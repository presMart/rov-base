"""
input_controller.py

Implements the InputController class for handling all gamepad/joystick input polling,
emergency stop lockout logic, and command dispatch to the ROV.
Ensures all operator input is processed at a configured rate and safely managed.
"""

import time
import logging

from .gamepad_input import GamepadInput

log = logging.getLogger(__name__)


class InputController:
    """
    Manages gamepad/joystick input polling and dispatches commands to the ROV.

    - Supports configurable polling rate (Hz) and E-stop lockout duration.
    - Handles emergency stop lockout by suppressing joystick commands for a set period.
    - Integrates with GamepadInput for deadzone, thrust step, and button mapping logic.
    - Ensures robust and thread-safe command sending via the TelemetryClient.
    """

    def __init__(self, telemetry_client, cfg):
        """
        Args:
            telemetry_client: TelemetryClient instance for sending commands.
            cfg: Configuration object with:
                - input_poll_rate_hz (int): How often to poll gamepad input.
                - estop_duration (float): Lockout time (sec) after emergency stop.
        """
        self.cfg = cfg
        self.telemetry = telemetry_client
        self.poll_interval = 1.0 / cfg.input_poll_rate_hz
        self.last_poll_time = 0
        self.last_command = {}
        self.estop_active = False
        self.estop_clear_time = 0
        self.estop_duration = cfg.estop_duration

        try:
            self.input_source = GamepadInput(cfg)
            log.info("Gamepad input enabled.")
        except RuntimeError as e:
            self.input_source = None
            log.warning(f"Gamepad not available: {e}")

    def trigger_emergency_stop(self):
        """
        Activate the emergency stop lockout, sending all motors to zero and
        suppressing joystick input for estop_duration seconds.
        """
        log.warning("Emergency Stop activated! Motors set to zero.")
        self.estop_active = True
        self.estop_clear_time = time.time() + self.estop_duration
        self.telemetry.send_emergency_stop()
        self.last_command = {
            "motor_horizontal_left": 0,
            "motor_horizontal_right": 0,
            "motor_vertical_front": 0,
            "motor_vertical_rear": 0,
        }

    def clear_emergency_stop(self):
        """Clear the E-stop lockout and resume normal input polling."""
        log.info("Emergency Stop lockout cleared. Joystick input restored.")
        self.estop_active = False

    def poll_input(self):
        """
        Poll the gamepad/joystick for input and send updated thrust commands to the ROV.

        - Ignores input and sends zero thrust during E-stop lockout.
        - Only sends commands if they have changed or are nonzero.
        - ROV utilizes a fail-safe where all motors are set to zero if no command
        is received within the configured poll interval (handled ROV-side).
        """
        now = time.time()

        # E-Stop lockout logic
        if self.estop_active:
            # Keep sending all zeros during lockout period
            self.telemetry.send_emergency_stop()
            if now >= self.estop_clear_time:
                self.clear_emergency_stop()
            return

        if self.input_source is None:
            return

        if now - self.last_poll_time < self.poll_interval:
            return
        self.last_poll_time = now

        command = self.input_source.get_command()

        # Send command if (a) it's changed OR (b) it's non-zero to maintain motor state
        should_send = command != self.last_command or any(
            abs(val) > 0.01 for val in command.values()
        )

        if should_send:
            self.last_command = command.copy()
            self.telemetry.send_command({"command": "set_thrust", "motors": command})
            log.debug(f"Sent command: {command}")
