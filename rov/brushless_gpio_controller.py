import pigpio
import logging

log = logging.getLogger(__name__)

class GPIOBrushlessController:
    def __init__(self, motor_pins: dict[str, int]):
        self.pi = pigpio.pi()
        if not self.pi.connected:
            raise RuntimeError("Could not connect to pigpio daemon.")
        self.motor_pins = motor_pins

        for pin in self.motor_pins.values():
            self.pi.set_mode(pin, pigpio.OUTPUT)
            self.pi.set_PWM_frequency(pin, 50)  # 50 Hz servo signal

        log.info("Brushless GPIO controller initialized")

    def set_motor(self, name: str, pulse_us: int):
        pin = self.motor_pins.get(name)
        if pin is not None:
            self.pi.set_servo_pulsewidth(pin, pulse_us)
        else:
            log.warning(f"Unknown brushless motor: {name}")

    def stop_all(self):
        for name in self.motor_pins:
            self.set_motor(name, 1500)  # neutral

    def shutdown(self):
        self.stop_all()
        self.pi.stop()
