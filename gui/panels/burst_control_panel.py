"""
burst_control_panel.py

Defines the BurstControlPanel for sending quick, preset movement bursts to the ROV.
This panel provides single-click directional thrust commands, making it easy to
trigger forward, reverse, strafe (yaw), ascend, or descend maneuvers for predictable
movement in tight spaces.
"""

from PyQt6.QtWidgets import QGroupBox, QPushButton, QVBoxLayout, QGridLayout


class BurstControlPanel(QGroupBox):
    """
    Panel for issuing preset 'burst' thrust commands to the ROV.

    - Provides buttons for forward, reverse, strafe, ascend, and descend.
    - Each button sends a temporary thrust command with a configurable value.
    - Designed to allow quick, intuitive movement corrections or repositioning.
    """

    def __init__(self, client, parent=None, burst_thrust_val: float = 0.75):
        """
        Args:
            client: TelemetryClient or compatible, used to send burst commands.
            parent: Parent QWidget (optional).
            burst_thrust_val (float): Thrust magnitude for each burst (configurable).
        """
        super().__init__("Burst Control", parent)
        self.client = client

        layout = QVBoxLayout()
        self.setLayout(layout)

        grid = QGridLayout()
        layout.addLayout(grid)

        self.burst_thrust_val = burst_thrust_val

        # Define movement patterns and labels
        self.bursts = {
            "forward": (
                "\u2191",
                {
                    "motor_horizontal_left": self.burst_thrust_val,
                    "motor_horizontal_right": self.burst_thrust_val,
                },
            ),
            "reverse": (
                "\u2193",
                {
                    "motor_horizontal_left": -self.burst_thrust_val,
                    "motor_horizontal_right": -self.burst_thrust_val,
                },
            ),
            "strafe_left": (
                "\u2190",
                {
                    "motor_horizontal_left": -self.burst_thrust_val,
                    "motor_horizontal_right": self.burst_thrust_val,
                },
            ),
            "strafe_right": (
                "\u2192",
                {
                    "motor_horizontal_left": self.burst_thrust_val,
                    "motor_horizontal_right": -self.burst_thrust_val,
                },
            ),
            "ascend": (
                "\u2b71",
                {
                    "motor_vertical_front": self.burst_thrust_val,
                    "motor_vertical_rear": self.burst_thrust_val,
                },
            ),
            "descend": (
                "\u2b73",
                {
                    "motor_vertical_front": -self.burst_thrust_val,
                    "motor_vertical_rear": -self.burst_thrust_val,
                },
            ),
        }

        # Button layout (3 rows x 3 columns)
        positions = {
            "forward": (0, 1),
            "strafe_left": (1, 0),
            "strafe_right": (1, 2),
            "ascend": (2, 0),
            "reverse": (2, 1),
            "descend": (2, 2),
        }

        # Create and wire up burst buttons
        for action, (label, thrust) in self.bursts.items():
            btn = QPushButton(label)
            btn.setFixedSize(80, 50)
            btn.clicked.connect(lambda _, t=thrust: self.send_burst(t))
            row, col = positions[action]
            grid.addWidget(btn, row, col)

    def send_burst(self, thrust_dict):
        """
        Send a single burst thrust command to the ROV.

        Args:
            thrust_dict (dict): Dictionary mapping motor names to thrust values.
        """
        command = {"command": "set_thrust", "motors": thrust_dict}
        self.client.send_command(command)
