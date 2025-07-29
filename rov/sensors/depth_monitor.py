import logging
from adafruit_ads1x15.analog_in import AnalogIn

log = logging.getLogger(__name__)


class DepthMonitor:
    """
    Reads analog voltage from a 30 PSI pressure transducer and converts it to pressure.
    Sends raw PSI to telemetry; GUI handles depth conversion (fresh vs salt).
    """

    def __init__(self, ads, config):
        """
        Args:
            ads: ADS1115 ADC instance.
            channel (int): ADS input channel (0-3).
        """
        self.channel = AnalogIn(ads, config.adc_channel)
        self.v_min, self.v_max = config.voltage_range
        self.p_min, self.p_max = config.pressure_range_psi
        self.atmospheric_psi = config.atmospheric_psi

        self.voltage = None
        self.pressure_psi = None

    def read(self):
        """
        Read sensor voltage and convert to pressure in PSI.
        Returns:
            float: Raw pressure in PSI.
        """
        try:
            voltage = self.channel.voltage
            self.voltage = voltage
            if voltage is None:
                raise ValueError("No voltage reading from depth sensor.")

            if voltage < self.v_min or voltage > self.v_max:
                log.warning(f"[DepthMonitor] Out of range voltage: {voltage:.2f}V")
                self.pressure_psi = None
                return None

            span_v = self.v_max - self.v_min
            span_p = self.p_max - self.p_min
            self.pressure_psi = ((voltage - self.v_min) / span_v) * span_p + self.p_min
            return self.pressure_psi

        except Exception as e:
            log.error(f"[DepthMonitor] Read error: {e}")
            return None

    def get_telemetry(self):
        """
        Returns the latest pressure reading for telemetry output.
        Always includes pressure_psi, even if currently unavailable.
        """
        return {
            "pressure_psi": self.pressure_psi if self.pressure_psi is not None else 0.0,
            "depth_voltage": self.voltage if self.voltage is not None else 0.0,
        }
