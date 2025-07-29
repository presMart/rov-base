"""
controller.py

Implements the ROVController class for managing all motor outputs.
Handles command profiles, thrust limiting, voltage failsafes, and emergency stops.
Intended to be used as the main motor interface for the ROV's async event loop.
"""

import logging
import time
import pigpio

# Configure logging
log = logging.getLogger(__name__)


class ROVController:
    """
    Controls the ROV's motors using both PCA9685 (brushed) and pigpio GPIO (brushless).
    Supports:
      - Normalized thrust commands
      - Burst limiting & smoothing
      - Voltage-limited failsafes
    """

    def __init__(self, pwm_driver, config):
        self.pwm = pwm_driver
        self.config = config
        self.motor_channels = config.motor_channels
        self.motor_smoothing_factor = config.motor_smoothing_factor
        self.pwm_min = config.pwm_min
        self.pwm_max = config.pwm_max
        self.pwm_neutral = config.pwm_neutral
        self.pwm_freq = config.pwm_freq
        self.motor_states = {name: 0.0 for name in self.motor_channels}
        self.voltage_limited = False

        self.pi = pigpio.pi()
        self.brushless_gpio_map = {}

        self.pwm.frequency = self.pwm_freq

        for name, motor in self.motor_channels.items():
            if motor["type"] == "brushless":
                gpio = motor["channel"]  # Treated as GPIO pin
                self.brushless_gpio_map[name] = gpio
                self.pi.set_mode(gpio, pigpio.OUTPUT)
                self.pi.set_servo_pulsewidth(gpio, self.pwm_neutral)
            else:
                channel = motor["channel"]
                self.pwm.channels[channel].duty_cycle = self._us_to_pwm(self.pwm_neutral)

        time.sleep(1.0)
        self.stop_all_motors()

    def _thrust_to_us(self, thrust: float) -> int:
        """Convert normalized thrust (-1.0 to 1.0) to pulse width in microseconds."""
        thrust = max(min(thrust, 1.0), -1.0)
        if thrust == 0.0:
            return self.pwm_neutral
        elif thrust > 0.0:
            return int(self.pwm_neutral + (self.pwm_max - self.pwm_neutral) * thrust)
        else:
            return int(self.pwm_neutral - (self.pwm_neutral - self.pwm_min) * abs(thrust))

    def _thrust_to_pwm(self, thrust: float) -> int:
        """Convert normalized thrust to PCA9685 12-bit PWM value."""
        return self._us_to_pwm(self._thrust_to_us(thrust))

    def _us_to_pwm(self, microseconds: int) -> int:
        """Convert microseconds to a 12-bit PWM duty cycle for PCA9685."""
        period_us = 1_000_000 / self.pwm_freq
        return int((microseconds / period_us) * 65535)

    def set_motor(self, name: str, thrust: float):
        """
        Apply thrust to a motor, clamping and routing appropriately.

        Brushless motors get GPIO pigpio output.
        Brushed motors use PWM hat channel.
        """
        motor_info = self.motor_channels.get(name)
        if not motor_info:
            log.warning(f"[ROVController] Unknown motor: {name}")
            return

        motor_type = motor_info.get("type", "brushed")
        thrust = max(min(thrust, 1.0), -1.0)

        if motor_type == "brushless":
            if thrust < 0:
                log.debug(f"[ROVController] Clamping reverse thrust for brushless motor '{name}'")
                thrust = 0.0
            pwm_us = self._thrust_to_us(thrust)
            gpio = motor_info.get("gpio") or self.brushless_gpio_map.get(name)
            if gpio is not None:
                self.pi.set_servo_pulsewidth(gpio, pwm_us)
            else:
                log.warning(f"[ROVController] No GPIO defined for brushless motor '{name}'")
        else:
            pwm_val = self._thrust_to_pwm(thrust)
            channel = motor_info.get("channel")
            if channel is not None:
                self.pwm.channels[channel].duty_cycle = pwm_val
            else:
                log.warning(f"[ROVController] No channel defined for brushed motor '{name}'")

        self.motor_states[name] = thrust

    def stop_all_motors(self):
        """Stop all motors by setting thrust to zero."""
        for name in self.motor_channels:
            self.set_motor(name, 0.0)

    def apply_command_profile(self, thrust_dict: dict):
        """Apply a smoothed command profile to all motors."""
        if self.voltage_limited:
            log.warning("[Controller] Ignoring motor command due to voltage-limited mode.")
            return
        for motor, thrust in thrust_dict.items():
            current = self.motor_states.get(motor, 0.0)
            smoothed = current + (thrust - current) * self.motor_smoothing_factor
            self.set_motor(motor, smoothed)

    def get_motor_states(self) -> dict:
        """Return most recent thrust values per motor."""
        return self.motor_states.copy()

    def get_telemetry(self) -> dict:
        """Compile motor state telemetry (voltage injected later)."""
        return {
            "voltage": None,
            "motor_state": self.get_motor_states(),
            "warnings": [],
            "status": "OK",
        }

    def set_voltage_limited(self, limited: bool):
        """Enable/disable motor commands based on low-voltage condition."""
        self.voltage_limited = limited
        if limited:
            self.stop_all_motors()

    def __del__(self):
        try:
            self.stop_all_motors()
        except Exception as e:
            log.warning(f"Exception during __del__: {e}")
        for gpio in self.brushless_gpio_map.values():
            self.pi.set_servo_pulsewidth(gpio, 0)
        self.pi.stop()
