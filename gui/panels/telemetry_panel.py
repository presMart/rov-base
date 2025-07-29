"""
telemetry_panel.py

Implements the TelemetryPanel for real-time ROV status display in the GUI.
Shows voltage, current mode, enclosure environment readings (temperature and humidity),
and motor thrust status/level.
Designed for clear at-a-glance diagnostics and easy extensibility.
"""

from PyQt6.QtWidgets import QVBoxLayout, QLabel, QGroupBox, QFormLayout


class TelemetryPanel(QGroupBox):
    """
    Panel displaying ROV telemetry information, including:

    - Main battery voltage and health status.
    - Environmental conditions in each enclosure (temperature, humidity).
    - Current motor thrust output for all channels.
    - Color-coded status indicators for easy operator alerting.
    """

    def __init__(self, parent=None):
        """
        Initialize the telemetry panel with pre-labeled sections for voltage,
        environment, and motors. Dynamic label creation allows for flexible
        sensor/motor configuration.
        """
        super().__init__("Telemetry", parent)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.voltage_label = QLabel("Voltage: -- V")
        self.status_label = QLabel("Status: OK")
        self.depth_label_fresh = QLabel("Depth (Freshwater): -- m")
        self.depth_label_salt = QLabel("Depth (Saltwater): -- m")

        self.env_labels = {}  # e.g., {"esc_box": QLabel()}

        layout.addWidget(self.voltage_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.depth_label_fresh)
        layout.addWidget(self.depth_label_salt)

        self.env_group = QGroupBox("Enclosure Conditions")
        self.env_layout = QFormLayout()
        self.env_group.setLayout(self.env_layout)
        layout.addWidget(self.env_group)

        self.motor_group = QGroupBox("Motor Thrusts")
        self.motor_layout = QFormLayout()
        self.motor_group.setLayout(self.motor_layout)
        layout.addWidget(self.motor_group)

        self.motor_labels = {}

    def update_telemetry(self, data: dict):
        """
        Update the panel with new telemetry data.

        Args:
            data (dict): Dictionary with voltage, voltage_mode, environment readings,
                         and motor thrust state. Structure:

                {
                    "voltage": float,
                    "voltage_mode": "normal"|"limited"|"critical",
                    "env": { <enclosure>: { "temp": float, "humidity": float } },
                    "motor_state": { <motor_name>: float }
                }
        """
        voltage = data.get("voltage")
        if voltage is not None:
            self.voltage_label.setText(f"Voltage: {voltage:.2f} V")
        else:
            self.voltage_label.setText("Voltage: -- V")

        pressure = data.get("pressure_psi")
        if pressure is not None:
            # Subtract atmospheric pressure and convert to depth
            freshwater_depth = max((pressure - 14.7) * 2.31 * 0.3048, 0.0)  # m
            saltwater_depth = max((pressure - 14.7) * 2.25 * 0.3048, 0.0)  # m

            self.depth_label_fresh.setText(
                f"Depth (Freshwater): {freshwater_depth:.2f} m"
            )
            self.depth_label_salt.setText(f"Depth (Saltwater): {saltwater_depth:.2f} m")
        else:
            self.depth_label_fresh.setText("Depth (Freshwater): -- m")
            self.depth_label_salt.setText("Depth (Saltwater): -- m")

        mode = data.get("voltage_mode", "normal")
        if mode == "limited":
            self.status_label.setText("LOW VOLTAGE: LIMITED MODE")
            self.status_label.setStyleSheet("color: orange")
        elif mode == "critical":
            self.status_label.setText("CRITICAL VOLTAGE: SHUTDOWN IMMINENT")
            self.status_label.setStyleSheet("color: red")
        else:
            self.status_label.setText("Status: OK")
            self.status_label.setStyleSheet("color: green")

        env = data.get("env", {})
        for name, vals in env.items():
            label = self.env_labels.get(name)
            if label is None:
                label = QLabel()
                self.env_layout.addRow(name, label)
                self.env_labels[name] = label

            temp = vals.get("temp", "--")
            hum = vals.get("humidity", "--")
            label.setText(f"{temp:.1f} °C / {hum:.1f} %")

        motors = data.get("motor_state", {})
        for name, val in motors.items():
            label = self.motor_labels.get(name)
            if label is None:
                label = QLabel()
                self.motor_layout.addRow(name, label)
                self.motor_labels[name] = label
            label.setText(f"{val:.2f}")
