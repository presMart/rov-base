"""
telemetry_client.py

Implements TelemetryClient for TCP socket communication between the GUI and ROV.
Handles command sending, telemetry reception, and robust reconnection logic.
Uses JSON-over-TCP, one message per line (Newline-delimited JSON).
"""

import socket
import json
import threading
import select

from gui.utils.logger import GuiLoggerAdapter


class TelemetryClient:
    """
    TCP client for communicating with the ROV controller.

    - Sends JSON-formatted commands to ROV (set thrust, emergency stop, shutdown...).
    - Receives JSON telemetry packets from the ROV.
    - Implements robust reconnection and thread-safe send/receive logic.
    - Can be shared by multiple GUI components (thread-safe).
    """

    def __init__(
        self, telemetry_host: str = "192.168.1.225", port: int = 9999, logger=None
    ):
        """
        Args:
            host (str): ROV IP or hostname.
            port (int): TCP port on ROV.
            logger: Optional logger or GUI log panel for logging connection events.
        """
        self.host = telemetry_host
        self.port = port
        self.logger = GuiLoggerAdapter(logger)
        self.socket = None
        self.lock = threading.Lock()
        self.recv_buffer = ""
        self.connect()

    def connect(self):
        """Establish a new TCP connection to the ROV."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(2.0)
        try:
            self.socket.connect((self.host, self.port))
        except Exception as e:
            self.logger.log(f"[TelemetryClient] Connection error: {e}")
            self.socket = None

    def send_command(self, command: dict):
        """
        Send a JSON command to the ROV.

        Args:
            command (dict): Command dictionary to serialize and send.
        """
        if not self.socket:
            return
        try:
            with self.lock:
                self.socket.sendall(json.dumps(command).encode("utf-8") + b"\n")
        except Exception as e:
            self.logger.log(f"[TelemetryClient] Failed to send command: {e}")

    def receive_telemetry(self) -> dict:
        """
        Attempt to receive and parse a JSON telemetry message from the ROV.

        Returns:
            dict: Most recent valid telemetry message (or {} if none available).
        """
        if not self.socket:
            return {}

        try:
            ready = select.select([self.socket], [], [], 0.01)  # Wait max 10ms
            if ready[0]:
                chunk = self.socket.recv(4096).decode("utf-8")
                if not chunk:
                    return {}
                self.recv_buffer += chunk

            if "\n" not in self.recv_buffer:
                return {}

            lines = self.recv_buffer.split("\n")
            self.recv_buffer = lines[-1]  # Save any incomplete line

            latest_valid = None
            for line in lines[:-1]:
                line = line.strip()
                if not line:
                    continue
                try:
                    latest_valid = json.loads(line)
                except json.JSONDecodeError as e:
                    self.logger.log(f"[TelemetryClient] JSON decode error: {e}")

            return latest_valid if latest_valid else {}
        except Exception as e:
            self.logger.log(f"[TelemetryClient] Failed to receive telemetry: {e}")
            return {}

    def close(self):
        """Close the current socket connection."""
        if self.socket:
            self.socket.close()
            self.socket = None

    def reconnect(self):
        """
        Attempt to reconnect to the ROV (closing and reopening the socket).
        Logs the result and resets internal buffers.
        """
        self.logger.log("[TelemetryClient] Attempting to reconnect...")
        self.close()
        self.recv_buffer = ""
        try:
            self.connect()
            if self.socket:
                self.logger.log("[TelemetryClient] Reconnection successful.")
            else:
                self.logger.log("[TelemetryClient] Reconnection failed.")
        except Exception as e:
            self.logger.log(f"[TelemetryClient] Reconnection error: {e}")

    def send_emergency_stop(self):
        # All motors to zero
        stop_cmd = {"command": "emergency_stop"}
        self.send_command(stop_cmd)

    def send_shutdown_pi(self):
        shutdown_cmd = {"command": "shutdown_pi"}
        self.send_command(shutdown_cmd)

    def send_restart_pi(self):
        restart_cmd = {"command": "restart_pi"}
        self.send_command(restart_cmd)
