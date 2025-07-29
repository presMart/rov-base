"""
monitoring.py

Implements voltage and environment monitoring for the ROV.
Includes voltage failsafe logic, DHT (temperature/humidity) sensor polling,
and async tasks for integration with the main event loop.
Designed for safe battery management and enclosure health tracking.
"""

import asyncio
import time
import threading
from adafruit_ads1x15.analog_in import AnalogIn
import logging

import adafruit_dht
import board

log = logging.getLogger(__name__)


class VoltageMonitor:
    """
    Monitors battery voltage, tracks warning/limited/critical thresholds,
    and manages failsafes including motor shutoff and shutdown callbacks.
    Handles noisy readings by requiring repeated low-voltage events over time.
    """

    def __init__(
        self,
        adc,
        warning_threshold,
        limited_threshold,
        critical_threshold,
        channel=0,
        critical_count=3,
        critical_delay=2.0,
        verify_delay=5.0,
        limited_count=3,
        limited_delay=2.0,
    ):
        """
        Args:
            adc: Analog-to-digital converter instance.
            warning_threshold (float): Warn operator if voltage < this value.
            limited_threshold (float): Enable limited mode if voltage < this value.
            critical_threshold (float): Shutdown/failsafe if voltage < this value.
            channel (int): ADC channel for voltage.
            critical_count (int): Events required before triggering shutdown.
            critical_delay (float): Min time between critical events (seconds).
            verify_delay (float): Wait time before verifying persistent voltage drop.
            limited_count (int): Events required before enabling limited mode.
            limited_delay (float): Min time between limited mode events (seconds).
        """
        self.adc = adc
        self.channel = channel
        self.warning = warning_threshold
        self.limited = limited_threshold
        self.critical = critical_threshold
        self.last_voltage = None
        self.shutdown_callback = None
        self.divider_ratio = 5.0
        self.adc_gain = 1
        self.ref_voltage = 4.096
        self.chan = AnalogIn(adc, self.channel)
        self.critical_count = critical_count
        self.critical_delay = critical_delay
        self.verify_delay = verify_delay
        self.limited_count = limited_count
        self.limited_delay = limited_delay
        self.low_v_times = []
        self.limited_v_times = []
        self.in_limited_mode = False

    def read_voltage(self):
        """
        Read and return the most recent voltage (in volts), after scaling
        for divider ratio. Also updates last_voltage for failsafe checks.
        """
        measured = self.chan.voltage
        actual_voltage = measured * self.divider_ratio
        self.last_voltage = actual_voltage
        return actual_voltage

    def check_voltage(self, rov=None):
        """
        Blocking voltage check for command loop or polling thread.

        - Warns if voltage < warning.
        - Enters limited mode if voltage < limited threshold repeatedly.
        - On critical, stops all motors, waits, rechecks, and triggers
            shutdown callback if needed.
        - Recovers modes if voltage returns to safe.
        """
        now = time.monotonic()
        if self.last_voltage is None:
            return

        if self.last_voltage < self.warning:
            log.warning(
                f"[WARNING] Battery low! Surface immediately! ({self.last_voltage:.2f}V)"
            )

        if self.last_voltage < self.limited:
            if not self.limited_v_times or (
                now - self.limited_v_times[-1] > self.limited_delay
            ):
                self.limited_v_times.append(now)
                log.info(
                    f"[LIMITED] Voltage below limited threshold: {self.last_voltage:.2f}V"
                )
            self.limited_v_times = [
                t
                for t in self.limited_v_times
                if now - t < (self.limited_delay * self.limited_count * 2)
            ]
            if (
                len(self.limited_v_times) >= self.limited_count
                and not self.in_limited_mode
            ):
                log.warning("[LIMITED] Sustained low voltage — disabling motors.")
                self.in_limited_mode = True
                if rov:
                    rov.set_voltage_limited(True)
        elif self.in_limited_mode:
            log.info(
                "[RECOVERY] Voltage back in normal range. Re-enabling motor control."
            )
            self.in_limited_mode = False
            self.limited_v_times.clear()
            if rov:
                rov.set_voltage_limited(False)

        if self.last_voltage < self.critical:
            if not self.low_v_times or (
                now - self.low_v_times[-1] > self.critical_delay
            ):
                self.low_v_times.append(now)
                log.warning(
                    f"[CRITICAL] Battery voltage below critical: {self.last_voltage:.2f}V, "
                    f"count={len(self.low_v_times)}"
                )
            self.low_v_times = [
                t
                for t in self.low_v_times
                if now - t < (self.critical_delay * self.critical_count * 2)
            ]
            if len(self.low_v_times) >= self.critical_count:
                log.critical(
                    "[CRITICAL] Multiple low-voltage events detected; stopping all motors."
                )
                if rov:
                    rov.stop_all_motors()
                time.sleep(self.verify_delay)
                measured = self.chan.voltage
                actual_voltage = measured * self.divider_ratio
                log.critical(
                    f"[VERIFY] Voltage after motor stop: {actual_voltage:.2f}V"
                )
                if actual_voltage < self.critical:
                    log.critical(
                        "[CRITICAL] Confirmed persistent low voltage—shutting down."
                    )
                    if self.shutdown_callback:
                        self.shutdown_callback()
                else:
                    log.warning(
                        "[RECOVERED] Voltage returned to safe level."
                    )
                    self.low_v_times = []
        else:
            self.low_v_times = []

    async def async_check_voltage(self, rov=None):
        """
        Async version for event loop usage (non-blocking waits).
        Behavior mirrors check_voltage(), but uses await on verify_delay.
        """
        now = time.monotonic()
        if self.last_voltage is None:
            return

        if self.last_voltage < self.warning:
            log.warning(
                f"[WARNING] Battery voltage low! Surface immediately! ({self.last_voltage:.2f}V)"
            )

        if self.last_voltage < self.limited:
            if not self.limited_v_times or (
                now - self.limited_v_times[-1] > self.limited_delay
            ):
                self.limited_v_times.append(now)
                log.info(
                    f"[LIMITED] Voltage below limited threshold: {self.last_voltage:.2f}V"
                )
            self.limited_v_times = [
                t
                for t in self.limited_v_times
                if now - t < (self.limited_delay * self.limited_count * 2)
            ]
            if (
                len(self.limited_v_times) >= self.limited_count
                and not self.in_limited_mode
            ):
                log.warning("[LIMITED] Sustained low voltage — disabling motors.")
                self.in_limited_mode = True
                if rov:
                    rov.stop_all_motors()
        elif self.in_limited_mode:
            log.info(
                "[RECOVERY] Voltage back in normal range. Re-enabling motor control."
            )
            self.in_limited_mode = False
            self.limited_v_times.clear()

        if self.last_voltage < self.critical:
            if not self.low_v_times or (
                now - self.low_v_times[-1] > self.critical_delay
            ):
                self.low_v_times.append(now)
                log.warning(
                    f"[CRITICAL] Battery voltage below critical: {self.last_voltage:.2f}V, "
                    f"count={len(self.low_v_times)}"
                )
            self.low_v_times = [
                t
                for t in self.low_v_times
                if now - t < (self.critical_delay * self.critical_count * 2)
            ]
            if len(self.low_v_times) >= self.critical_count:
                log.critical(
                    "[CRITICAL] Multiple low-voltage events detected; stopping all motors."
                )
                if rov:
                    rov.stop_all_motors()
                await asyncio.sleep(self.verify_delay)
                measured = self.chan.voltage
                actual_voltage = measured * self.divider_ratio
                log.critical(
                    f"[VERIFY] Voltage after motor stop: {actual_voltage:.2f}V"
                )
                if actual_voltage < self.critical:
                    log.critical(
                        "[CRITICAL] Confirmed persistent low voltage—shutting down."
                    )
                    if self.shutdown_callback:
                        self.shutdown_callback()
                else:
                    log.warning(
                        "[RECOVERED] Voltage returned to safe level."
                    )
                    self.low_v_times = []
        else:
            self.low_v_times = []

    def register_shutdown_callback(self, callback):
        """
        Register a callback (e.g., main.shutdown) to trigger
        if persistent critical voltage is detected.
        """
        self.shutdown_callback = callback

    def get_mode(self) -> str:
        """Get current voltage mode string ("critical", "limited", or "normal")."""
        if self.last_voltage < self.critical:
            return "critical"
        elif self.in_limited_mode:
            return "limited"
        return "normal"


async def async_voltage_monitor(monitor, rov, poll_interval=1.0):
    """
    Async voltage monitor. Periodically reads voltage, checks for low-voltage events,
    and triggers failsafes as needed.
    """
    log = logging.getLogger(__name__)
    while True:
        voltage = monitor.read_voltage()
        log.debug(f"Voltage: {voltage:.2f}V")
        await monitor.async_check_voltage(rov)
        await asyncio.sleep(poll_interval)


class DHTMonitor:
    """
    Threaded monitor for multiple DHT11/DHT22 sensors.

    - Maps each sensor by name to GPIO and sensor type.
    - Polls sensors at polling_interval, stores latest readings.
    - Can be safely started/stopped, handles sensor initialization and exit.
    """

    def __init__(self, sensor_map, polling_interval=10):
        """
        Args:
            sensor_map (dict): {name: {"gpio": int, "type": "DHT11"|"DHT22"}}
            polling_interval (int): Seconds between polls.
        """
        self.sensor_map = sensor_map
        self.polling_interval = polling_interval
        self.readings = {}
        self.sensors = {}  # key: sensor name, value: sensor object
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)

    def start(self):
        """Start polling all DHT sensors in a background thread."""
        log.info("Starting DHTMonitor thread...")
        self._initialize_sensors()
        self.thread.start()

    def stop(self):
        """Signal thread to stop and clean up sensor objects."""
        log.info("Stopping DHTMonitor and releasing sensors...")
        self.stop_event.set()
        self.thread.join()
        for name, sensor in self.sensors.items():
            try:
                sensor.exit()
                log.info(f"Sensor {name} on GPIO released.")
            except Exception as e:
                log.warning(f"Failed to release sensor {name}: {e}")

    def get_readings(self) -> dict:
        """Return a copy of all latest sensor readings as a dict."""
        return self.readings.copy()

    def _initialize_sensors(self):
        """Set up DHT sensors for each entry in sensor_map."""
        for name, cfg in self.sensor_map.items():
            gpio = cfg["gpio"]
            sensor_type = cfg.get("type", "DHT22")

            try:
                pin = getattr(board, f"D{gpio}")
                if sensor_type == "DHT11":
                    sensor = adafruit_dht.DHT11(pin)
                else:
                    sensor = adafruit_dht.DHT22(pin)
                self.sensors[name] = sensor
                log.info(f"Initialized {sensor_type} on GPIO{gpio} as '{name}'")
            except Exception as e:
                log.error(f"Failed to initialize {sensor_type} on GPIO{gpio}: {e}")

    def _monitor_loop(self):
        """
        Thread main loop: periodically poll all DHT sensors and update readings.
        Handles recoverable read errors, logs persistent failures.
        """
        log.info("DHTMonitor loop starting... stabilizing sensors.")
        time.sleep(2)

        while not self.stop_event.is_set():
            for name, sensor in self.sensors.items():
                try:
                    temp = sensor.temperature
                    hum = sensor.humidity
                    if temp is not None and hum is not None:
                        self.readings[name] = {"temp": temp, "humidity": hum}
                        log.debug(
                            f"[{name}] Temp: {temp:.1f} °C, Humidity: {hum:.1f} %"
                        )
                    else:
                        log.warning(f"[{name}] No reading available.")
                except RuntimeError as e:
                    log.warning(f"[{name}] Sensor read failed (recoverable): {e}")
                except Exception as e:
                    log.error(f"[{name}] Sensor error: {e}")
            self.stop_event.wait(timeout=self.polling_interval)
