import logging
import pigpio

log = logging.getLogger(__name__)

class EscPowerManager:
    """
    Controls MOSFETs (via PWM) or SSRs (via GPIO) that gate power to the ESCs.
    """

    def __init__(self, pwm_driver=None, channels=None, gpio_pins=None):
        """
        Args:
            pwm_driver: Adafruit PCA9685 instance (optional)
            channels: List[int], PWM channels for MOSFET control (optional)
            gpio_pins: List[int], GPIO pin numbers for SSRs (optional)
        """
        self.pwm = pwm_driver
        self.channels = channels or []
        self.gpio_pins = gpio_pins or []
        self.enabled = False

        if self.gpio_pins:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                raise RuntimeError("Could not connect to pigpio daemon")
            for pin in self.gpio_pins:
                self.pi.set_mode(pin, pigpio.OUTPUT)

        self.disable()  # Ensure off on boot

    def enable(self):
        """Enable ESC power (PWM HIGH or GPIO HIGH)."""
        for ch in self.channels:
            self.pwm.channels[ch].duty_cycle = 0xFFFF
        for pin in self.gpio_pins:
            self.pi.write(pin, 1)
        self.enabled = True
        log.info("ESC power ENABLED")

    def disable(self):
        """Disable ESC power (PWM LOW or GPIO LOW)."""
        for ch in self.channels:
            self.pwm.channels[ch].duty_cycle = 0
        for pin in self.gpio_pins:
            self.pi.write(pin, 0)
        self.enabled = False
        log.info("ESC power DISABLED")

    def shutdown(self):
        """Cleanup pigpio if in use."""
        self.disable()
        if hasattr(self, 'pi'):
            self.pi.stop()

    # """
    # Controls MOSFETs that gate power to the ESCs using the PCA9685 PWM driver.

    # - Forces MOSFETs off on init.
    # - Provides methods to turn ESC power on or off.
    # - Helps prevent premature ESC startup during boot.
    # """

    # def __init__(self, pwm_driver, channels: list[int]):
    #     """
    #     Args:
    #         pwm_driver: Instance of Adafruit PCA9685.
    #         channels (list[int]): PCA9685 channels connected to MOSFET gates.
    #     """
    #     self.pwm = pwm_driver
    #     self.channels = channels
    #     self.enabled = False
    #     self.disable()  # Ensure off on boot

    # def enable(self):
    #     """Enable ESC power by setting 100% duty cycle (logic HIGH)."""
    #     for ch in self.channels:
    #         self.pwm.channels[ch].duty_cycle = 0xFFFF
    #     self.enabled = True
    #     log.info(f"ESC power ENABLED on channels {self.channels}")

    # def disable(self):
    #     """Disable ESC power by setting 0% duty cycle (logic LOW)."""
    #     for ch in self.channels:
    #         self.pwm.channels[ch].duty_cycle = 0
    #     self.enabled = False
    #     log.info(f"ESC power DISABLED on channels {self.channels}")
