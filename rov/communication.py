"""
communication.py

Implements CommunicationManager, the async TCP server for the ROV.
Handles client authentication, JSONL/NDJSON command reception, and telemetry streaming.
Integrates with main event loop for robust, low-latency command/telemetry exchange.
"""

import asyncio
import json
import logging
from typing import Optional, Any

log = logging.getLogger(__name__)


class CommunicationManager:
    """
    Asynchronous TCP server for ROV command and telemetry exchange.

    - Accepts incoming connections from trusted clients only (configurable IPs/subnets).
    - Receives JSONL/NDJSON commands, parsed line-by-line.
    - Sends telemetry updates to the connected client as JSONL.
    - Handles connection lifecycle and error logging.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9000,
        trusted_clients: list[str] = ["0.0.0.0"],
    ):
        """
        Args:
            host (str): IP address or hostname to bind to (usually "0.0.0.0").
            port (int): TCP port to listen for connections.
            trusted_clients (list[str]): List of IPs or subnet prefixes to allow.
        """
        self.host = host
        self.port = port
        self.trusted_clients = trusted_clients
        # self.reader = None
        # self.writer = None
        # self.server = None
        self.connected = False
        self.server: Optional[asyncio.base_events.Server] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def start_server(self):
        """
        Start the TCP server and accept a single client at a time.
        Waits for a trusted client before proceeding.
        """
        self.server = await asyncio.start_server(
            self._handle_client, self.host, self.port
        )
        log.info(f"Server started on {self.host}:{self.port}")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """
        Accept and authenticate a client connection, storing reader/writer
        if IP is trusted. Otherwise, reject the connection.
        """
        addr = writer.get_extra_info("peername")
        if not addr or not self._is_trusted(addr[0]):
            log.warning(f"Rejected connection from untrusted IP: {addr}")
            writer.close()
            await writer.wait_closed()
            return
        self._reader = reader
        self._writer = writer
        self.connected = True
        log.info("Client connected")

    def _is_trusted(self, ip: str) -> bool:
        """
        Check if the client's IP address is in the trusted list.

        Args:
            ip (str): Client IP address.
        Returns:
            bool: True if trusted, False otherwise.
        """
        for trusted in self.trusted_clients:
            if ip.startswith(trusted):
                return True
        return False

    async def handle_connection(self) -> Optional[Any]:
        """
        Wait for and parse a single command from the connected client.

        Returns:
            dict or None: The parsed JSON command, or None if no command.
        """
        # if not self.connected or self.reader.at_eof():
        #     return None
        if not self._reader:
            await asyncio.sleep(0.05)
            return None
        try:
            line = await asyncio.wait_for(self._reader.readline(), timeout=0.01)
            if not line:
                return None
            try:
                return json.loads(line.decode("utf-8").strip())
            except Exception as e:
                log.warning(f"Failed to parse JSON command: {e}")
        except asyncio.TimeoutError:
            return None

    async def send_telemetry(self, telemetry: dict):
        """
        Send a JSON telemetry dictionary to the connected client.

        Args:
            telemetry (dict): Telemetry data to send.
        """
        if not self._writer:
            return
        try:
            message = json.dumps(telemetry) + "\n"
            self._writer.write(message.encode("utf-8"))
            await self._writer.drain()
        except Exception as e:
            log.warning(f"Failed to send telemetry: {e}")

        # if self.writer is None or self.writer.is_closing():
        #     return
        # try:
        #     payload = json.dumps(telemetry_dict) + "\n"
        #     log.info(f"[COMM] Sending telemetry: {payload.strip()}")
        #     self.writer.write(payload.encode())
        #     await self.writer.drain()
        # except Exception as e:
        #     log.error(f"Telemetry send failed: {e}")

    # async def send_error(self, message):
    #     if self.writer is None or self.writer.is_closing():
    #         return
    #     error_payload = json.dumps({"error": message}) + "\n"
    #     self.writer.write(error_payload.encode())
    #     await self.writer.drain()

    # def _validate_command(self, command):
    #     if not isinstance(command, dict):
    #         return False
    #     if "command" not in command:
    #         return False
    #     if command["command"] == "set_thrust":
    #         if "motors" not in command or not isinstance(command["motors"], dict):
    #             return False
    #     return True
