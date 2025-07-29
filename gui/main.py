"""
main.py

Entry point for the ROV GUI application.
Sets up the main application window, initializes panels, and manages resource lifecycle
for telemetry, input, video streaming, and logging.

Usage:
    python -m gui.main
"""

from PyQt6.QtWidgets import QApplication, QTabWidget, QMessageBox
from PyQt6.QtCore import QTimer
import sys
import logging

from config import load_config
from logging_setup import setup_logging
from gui.panels.app_window import AppWindow
from gui.panels.video_panel import VideoPanel
from gui.panels.telemetry_panel import TelemetryPanel
from gui.panels.burst_control_panel import BurstControlPanel
from gui.input.input_controller import InputController
from gui.panels.logging_panel import LoggingPanel
from gui.communication.telemetry_client import TelemetryClient
from gui.utils.logger import GuiLogHandler


setup_logging(logfile="rov_gui.log")
logger = logging.getLogger(__name__)


def main():
    """
    Launch the ROV's GUI application.

    - Loads configuration and sets up logging.
    - Initializes main app window and panels (logging, gampad control, video, etc.).
    - Sets up timers for polling telemetry and input.
    - Connects emergency stop, Pi shutdown, restart, and reconnect buttons to handlers.
    - Manages resource lifecycles on reconnects to avoid leaks or frozen panels.
    """
    config = load_config()
    app = QApplication(sys.argv)

    logging_panel = LoggingPanel(max_lines=config.logging_max_lines)
    client = TelemetryClient(config.telemetry_host, config.port, logging_panel)
    input_controller = InputController(client, config)

    window = AppWindow(client, logging_panel)
    layout = window.layout()
    telemetry_poll_rate_ms = config.telemetry_poll_rate_ms

    # Panels as window attributes for robust replacement
    window.video_panel = VideoPanel(
        config.camera_stream_url, camera_resolution=config.camera_resolution
    )
    window.telemetry_panel = TelemetryPanel()
    window.set_video_widget(window.video_panel)
    window.set_telemetry_widget(window.telemetry_panel)

    gui_handler = GuiLogHandler()
    gui_handler.setLevel(logging.INFO)
    gui_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    gui_handler.emitter.log_signal.connect(logging_panel.append_log)
    logging.getLogger().addHandler(gui_handler)

    motor_tabs = QTabWidget()
    motor_tabs.addTab(
        BurstControlPanel(client, burst_thrust_val=config.burst_thrust_val),
        "Burst Control",
    )
    layout.addWidget(motor_tabs)
    layout.addWidget(logging_panel)

    assert window.telemetry_panel is not None

    def update():
        """Polls telemetry data from the ROV and updates the GUI panels."""
        data = client.receive_telemetry()
        if data:
            window.telemetry_panel.update_telemetry(data)
            if log_msg := data.get("log"):
                logging_panel.append_log(log_msg)

    window.telemetry_timer = QTimer()
    window.telemetry_timer.timeout.connect(update)
    window.telemetry_timer.start(telemetry_poll_rate_ms)

    window.input_timer = QTimer()
    window.input_timer.setInterval(10)  # 100Hz
    window.input_timer.timeout.connect(
        lambda: input_controller.poll_input() if window.is_gamepad_enabled() else None
    )
    window.input_timer.start()

    # Emergency stop button handler
    window.emergency_button.clicked.connect(
        lambda: [
            input_controller.trigger_emergency_stop(),
            logging_panel.append_log(
                "[USER] Emergency Stop: All motors set to zero (lockout active)."
            ),
        ]
    )

    # Pi safe shutdown button handler
    def handle_shutdown_pi():
        reply = QMessageBox.question(
            window,
            "Shutdown Pi?",
            "Are you sure you want to shutdown the ROV and Raspberry Pi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            client.send_shutdown_pi()
            logging_panel.append_log("[USER] Shutdown command sent to ROV.")

    window.shutdown_button.clicked.connect(handle_shutdown_pi)

    # Restart Pi button handler
    def handle_restart_pi():
        reply = QMessageBox.question(
            window,
            "Restart Pi?",
            "Are you sure you want to restart the ROV and Raspberry Pi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            client.send_restart_pi()
            logging_panel.append_log("[USER] Restart command sent to ROV.")

    window.restart_button.clicked.connect(handle_restart_pi)

    # Robust reconnect logic for clean panel/timer resets and leak avoidance
    def handle_reconnect():
        """
        Handle reconnect logic for the ROV GUI.

        - Reconnects network client.
        - Stops and cleans up all panels/timers.
        - Re-creates video and telemetry panels and timers.
        """
        client.reconnect()
        logging_panel.append_log("[INFO] Reconnection attempt initiated.")

        # Stop timers
        if hasattr(window, "telemetry_timer"):
            window.telemetry_timer.stop()
        if hasattr(window, "input_timer"):
            window.input_timer.stop()

        # Stop old video panel to release resources
        if hasattr(window, "video_panel") and hasattr(window.video_panel, "stop"):
            window.video_panel.stop()

        # Re-create panels
        window.video_panel = VideoPanel(
            config.camera_stream_url, camera_resolution=config.camera_resolution
        )
        window.telemetry_panel = TelemetryPanel()
        window.set_video_widget(window.video_panel)
        window.set_telemetry_widget(window.telemetry_panel)

        # Restart timers, now pointing at the new panels
        def update():
            data = client.receive_telemetry()
            if data:
                window.telemetry_panel.update_telemetry(data)
                if log_msg := data.get("log"):
                    logging_panel.append_log(log_msg)

        window.telemetry_timer = QTimer()
        window.telemetry_timer.timeout.connect(update)
        window.telemetry_timer.start(telemetry_poll_rate_ms)

        window.input_timer = QTimer()
        window.input_timer.setInterval(10)
        window.input_timer.timeout.connect(
            lambda: (
                input_controller.poll_input() if window.is_gamepad_enabled() else None
            )
        )
        window.input_timer.start()

    # Disconnect previous signal if present, then connect robust handler
    try:
        window.reconnect_button.clicked.disconnect()
    except Exception:
        pass  # Not previously connected, ignore
    window.reconnect_button.clicked.connect(handle_reconnect)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
