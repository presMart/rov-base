"""
main.py

Main entry point for the ROV onboard controller. Initializes hardware interfaces,
configures the control/monitoring stack, and runs the async network loop to
accept commands and stream telemetry to the GUI.
Supports robust voltage monitoring, environmental sensing, and safe shutdown/reboot.
"""

import threading
import asyncio
import time
import subprocess
import logging
from typing import Any
import pigpio
import os

from rov.utils.esc_power_manager import EscPowerManager
from .controller import ROVController
from .sensors.monitoring import VoltageMonitor, async_voltage_monitor, DHTMonitor
from .sensors.depth_monitor import DepthMonitor
from .communication import CommunicationManager
from config import load_config
from logging_setup import setup_logging

from adafruit_pca9685 import PCA9685
from adafruit_ads1x15.ads1115 import ADS1115
import board
import busio


config = load_config()

setup_logging(logfile="rov_pi.log")
logger = logging.getLogger(__name__)

# Ensure pigpiod is running
if os.system("pgrep pigpiod > /dev/null") != 0:
    logger.info("Starting pigpiod daemon...")
    os.system("sudo pigpiod")
    time.sleep(1)  # Give it a moment to initialize
else:
    logger.info("pigpiod daemon already running.")


def perform_shutdown(rov):
    """
    Gracefully stop all motors and power off the Raspberry Pi.
    Called on critical voltage or remote shutdown command.
    """
    log = logging.getLogger(__name__)
    log.critical(
        "Performing emergency shutdown in 10 seconds!"
    )  # Delay for potential future "cancel shutdown" feature
    rov.stop_all_motors()
    esc_power.disable()
    time.sleep(10)
    log.critical("Shutting down system now...")
    subprocess.run(["sudo", "shutdown", "now"])


def perform_reboot(rov):
    """
    Gracefully stop all motors and reboot the Raspberry Pi.
    Called on remote restart command.
    """
    log = logging.getLogger(__name__)
    log.critical("Performing system reboot in 5 seconds!")
    rov.stop_all_motors()
    esc_power.disable()
    time.sleep(5)
    log.critical("Rebooting system now...")
    subprocess.run(["sudo", "reboot"])


async def async_network_loop(comm, rov_controller, v_monitor):
    """
    Main asyncio event loop for handling incoming commands and sending telemetry.

    - Accepts JSONL/NDJSON commands from GUI client.
    - Updates motor states, processes emergency stop/shutdown/reboot.
    - Periodically sends telemetry (voltage, environment, motor state) to GUI.
    - Integrates voltage/environment monitoring with command control.
    """
    log = logging.getLogger(__name__)
    await comm.start_server()
    log.info("Async network loop running")

    voltage_task = asyncio.create_task(
        async_voltage_monitor(
            v_monitor,
            rov_controller,
            poll_interval=1.0,
        )
    )

    last_command_time = time.monotonic()
    command_timeout = 0.5
    telemetry: dict[str, Any] = {}
    last_telemetry_time = 0.0

    try:
        while True:
            try:
                try:
                    # Wait up to 0.01s for a command, then continue
                    command = await asyncio.wait_for(
                        comm.handle_connection(), timeout=0.01
                    )
                except asyncio.TimeoutError:
                    command = None
                now = time.monotonic()
                telemetry.clear()
                if isinstance(command, dict):
                    last_command_time = now
                    cmd_type = command.get("command")

                    if cmd_type == "set_thrust":
                        motors = command.get("motors", {})
                        rov_controller.apply_command_profile(motors)
                        telemetry["motor_state"] = motors
                        telemetry["actual"] = rov_controller.get_motor_states()
                    elif cmd_type == "emergency_stop":
                        rov_controller.stop_all_motors()
                        log.warning("Emergency stop received from GUI.")
                    elif cmd_type == "shutdown_pi":
                        log.warning(
                            "Shutdown command received. Shutting down ROV in 10 seconds..."
                        )
                        await comm.send_telemetry(
                            {"log": "ROV shutting down (shutdown_pi command received)."}
                        )
                        # perform_shutdown runs background thread to avoid blocking event loop
                        threading.Thread(
                            target=perform_shutdown, args=(rov_controller,), daemon=True
                        ).start()
                    elif cmd_type == "restart_pi":
                        log.warning(
                            "Restart command received. Rebooting ROV in 5 seconds..."
                        )
                        await comm.send_telemetry(
                            {"log": "ROV rebooting (restart_pi command received)."}
                        )
                        threading.Thread(
                            target=perform_reboot, args=(rov_controller,), daemon=True
                        ).start()
                    else:
                        log.warning(f"Unknown command type received: {cmd_type}")

                elif now - last_command_time > command_timeout:
                    rov_controller.stop_all_motors()

                depth_monitor.read()
                telemetry.update(depth_monitor.get_telemetry())
                telemetry.update(rov_controller.get_telemetry())
                telemetry["voltage"] = v_monitor.read_voltage()
                telemetry["voltage_mode"] = v_monitor.get_mode()

                telemetry["env"] = dht_monitor.get_readings()

                if now - last_telemetry_time >= 0.1:
                    await comm.send_telemetry(telemetry)
                    last_telemetry_time = now

                await asyncio.sleep(0.01)

            except (ConnectionResetError, BrokenPipeError):
                log.error(
                    "Connection lost. Stopping motors and waiting for new connection."
                )
                rov_controller.stop_all_motors()
                break
            except Exception as e:
                log.error(f"Unexpected error in async network loop: {e}")
                rov_controller.stop_all_motors()
                break
    finally:
        voltage_task.cancel()
        try:
            await voltage_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    """
    Initialize all hardware and monitoring components, then run the async network loop.
    Handles safe shutdown/reboot and resource cleanup on exit.
    """

    i2c = busio.I2C(board.SCL, board.SDA)
    pwm_driver = PCA9685(i2c)
    pwm_driver.frequency = config.pwm_freq

    esc_power = EscPowerManager(gpio_pins=[5, 6])
    esc_power.disable()  # Step 1: Turn off ESC power at boot
    time.sleep(2.0)      # Step 2: Let ESCs fully discharge

    adc = ADS1115(i2c)

    rov = ROVController(pwm_driver, config)  # Step 3: Send neutral PWM
    time.sleep(0.5)                          # Optional: slight buffer to stabilize PWM
    esc_power.enable()                       # Step 4: Power on ESCs with valid PWM

    voltage_monitor = VoltageMonitor(
        adc, config.voltage_warning, config.voltage_limited, config.voltage_critical
    )
    voltage_monitor.register_shutdown_callback(lambda: perform_shutdown(rov))
    depth_monitor = DepthMonitor(adc, config.depth_sensor)

    dht_monitor = DHTMonitor(config.dht_sensor_map, polling_interval=10)
    dht_monitor.start()

    comm = CommunicationManager(config.host, config.port, config.trusted_clients)

    try:
        asyncio.run(async_network_loop(comm, rov, voltage_monitor))
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    finally:
        rov.stop_all_motors()
        dht_monitor.stop()
