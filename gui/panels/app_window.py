"""
app_window.py

Defines the main application window for the ROV GUI, including layout and wiring for
core panels, control buttons, and toggling gamepad input (on by default).
Responsible for overall UI structure and top-level widget management.
"""

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QSpacerItem,
    QSizePolicy,
)
from PyQt6.QtCore import QTimer
from gui.communication.telemetry_client import TelemetryClient
from gui.panels.video_panel import VideoPanel
from gui.panels.telemetry_panel import TelemetryPanel


class AppWindow(QMainWindow):
    """
    Main application window for the ROV GUI.

    - Sets up and manages main layout, including video and telemetry panels.
    - Exposes attributes for buttons, timers, and gamepad toggle for wiring in main.py.
    - Supports robust widget replacement for reconnects and resource cleanup.
    """

    def __init__(self, client: TelemetryClient, logger=None):
        """Initialize AppWindow with telemetry client and optional logger."""
        super().__init__()
        self.setWindowTitle("ROV Control Panel")
        self.setMinimumSize(1024, 768)

        self.video_panel: VideoPanel | None = None
        self.telemetry_panel: TelemetryPanel | None = None

        self.telemetry_timer: QTimer | None = None
        self.input_timer: QTimer | None = None

        self.client = client
        self.logger = logger

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self._layout = QVBoxLayout()
        self.central_widget.setLayout(self._layout)

        self.top_row_layout = QHBoxLayout()
        self._layout.addLayout(self.top_row_layout)

        self.video_placeholder = QWidget()
        self.telemetry_placeholder = QWidget()
        self.top_row_layout.addWidget(self.video_placeholder)
        self.top_row_layout.addWidget(self.telemetry_placeholder)

        # Gamepad control toggle
        self.gamepad_checkbox = QCheckBox("Enable Gamepad Input")
        self.gamepad_checkbox.setChecked(True)
        self._layout.addWidget(self.gamepad_checkbox)

        # Button row
        self.button_layout = QHBoxLayout()
        self.emergency_button = QPushButton("Emergency Stop")
        self.shutdown_button = QPushButton("Shutdown Pi")
        self.restart_button = QPushButton("Restart Pi")
        self.reconnect_button = QPushButton("Reconnect")
        self.reconnect_button.clicked.connect(self.reconnect_to_rov)

        self.button_layout.addWidget(self.emergency_button)
        self.button_layout.addWidget(self.shutdown_button)
        self.button_layout.addWidget(self.restart_button)
        self.button_layout.addWidget(self.reconnect_button)

        self.button_layout.addItem(
            QSpacerItem(
                40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
            )
        )
        self._layout.addLayout(self.button_layout)

    def set_video_widget(self, widget):
        """
        Replace the current video widget with a new one.

        Args:
            widget (QWidget): New video widget to insert.
        """
        self.top_row_layout.replaceWidget(self.video_placeholder, widget)
        self.video_placeholder.deleteLater()
        self.video_placeholder = widget

    def set_telemetry_widget(self, widget):
        """
        Replace the current telemetry widget with a new one.

        Args:
            widget (QWidget): New telemetry widget to insert.
        """
        self.top_row_layout.replaceWidget(self.telemetry_placeholder, widget)
        self.telemetry_placeholder.deleteLater()
        self.telemetry_placeholder = widget

    def reconnect_to_rov(self):
        """
        Attempt to reconnect to the ROV network server.

        (Handler for 'Reconnect' button; robust reconnect logic is in main.py)
        """
        self.client.reconnect()
        if self.logger:
            self.logger.append_log("[INFO] Reconnection attempt initiated.")

    def layout(self):
        """Return the main QVBoxLayout for adding additional panels."""
        return self._layout

    def is_gamepad_enabled(self) -> bool:
        """
        Check if gamepad input is enabled via the toggle checkbox.

        Returns:
            bool: True if gamepad input is enabled, False otherwise.
        """
        return self.gamepad_checkbox.isChecked()
