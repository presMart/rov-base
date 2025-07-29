"""
gamepad_input.py

Provides the GamepadInput class for abstracting joystick/gamepad controls.
Handles deadzone logic, configurable thrust steps, and button-to-motor mapping.
Wraps pygame for reliable cross-platform controller input.
"""

import pygame
import logging

log = logging.getLogger(__name__)


class GamepadInput:
    """
    Handles gamepad/joystick input for ROV control.

    - Initializes pygame and joystick subsystem.
    - Supports configurable deadzone, thrust steps, and boost buttons.
    - Maps joystick axes and buttons to motor thrust commands.
    - Provides a uniform interface for polling the current command dictionary.
    """

    def __init__(self, cfg):
        """
        Args:
            cfg: Configuration object with gamepad parameters:
                - gamepad_deadzone (float)
                - gamepad_thrust_steps (list[float])
                - boost_buttons (list[int])
                - button_motor_map (dict[int, str])
        Raises:
            RuntimeError: If no joystick is detected on initialization.
        """
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No joystick detected")

        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        log.info(f"Initialized joystick: {self.joystick.get_name()}")

        self.cfg = cfg
        self.axis_deadzone = self.cfg.gamepad_deadzone
        self.thrust_steps = self.cfg.gamepad_thrust_steps
        self.button_motor_map = {
            6: "motor_vertical_front",
            7: "motor_vertical_rear",
            4: "motor_horizontal_left",
            5: "motor_horizontal_right",
        }
        self.boost_buttons = self.cfg.boost_buttons

    def _linear_thrust(self, value):
        """
        Apply deadzone logic and round axis input for stability.

        Args:
            value (float): Raw axis input from joystick.
        Returns:
            float: Thrust value after deadzone and rounding.
        """
        return 0.0 if abs(value) < self.axis_deadzone else round(value, 2)

    def get_command(self):
        """
        Poll the current joystick state and generate a thrust command dictionary.

        - Reads horizontal/vertical axes.
        - Normalizes for tank drive, applies deadzone.
        - Applies button overrides for horizontal/vertical motors.
        Returns:
            dict: {
                "motor_horizontal_left": float,
                "motor_horizontal_right": float,
                "motor_vertical_front": float,
                "motor_vertical_rear": float
            }
        """
        pygame.event.pump()

        lx = self.joystick.get_axis(0)
        ly = -self.joystick.get_axis(1)
        ry = -self.joystick.get_axis(3)

        # Linear thrusts with deadzone
        lx = self._linear_thrust(lx)
        ly = self._linear_thrust(ly)
        ry = self._linear_thrust(ry)

        # Combine left stick for horizontal (tank-style) movement
        left_thrust = ly + lx
        right_thrust = ly - lx

        # Normalize if any exceed 1.0
        max_val = max(abs(left_thrust), abs(right_thrust), 1.0)
        left_thrust = round(left_thrust / max_val, 2)
        right_thrust = round(right_thrust / max_val, 2)

        vertical_thrust = ry

        command = {
            "motor_horizontal_left": left_thrust,
            "motor_horizontal_right": right_thrust,
            "motor_vertical_front": vertical_thrust,
            "motor_vertical_rear": vertical_thrust,
        }

        # Override with buttons
        for button_index, motor in self.button_motor_map.items():
            if self.joystick.get_button(button_index):
                command[motor] = 1.0  # Full thrust for buttons

        return command
