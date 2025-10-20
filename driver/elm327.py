"""
ELM327 driver module for OBD-II communication.

This module provides an interface to communicate with ELM327-based OBD-II adapters.
"""

import threading
import time
from typing import Optional

from .exceptions import (
    ConnectionException as ELM327ConnectionException,
    DeviceNotFoundException,
    InvalidResponseException,
    NoResponseException,
    NotConnectedException,
)
from .isotp import parse_isotp_frames, parse_uds_response, IsoTpResponse
from .connection import Connection, ConnectionException


class ELM327:
    """
    Driver for ELM327-based OBD-II adapters.

    This class handles communication with ELM327 devices through an abstract connection
    interface, supporting both standard OBD-II requests and UDS (Unified Diagnostic Services)
    messages over ISO-TP protocol.

    Attributes:
        connection (Connection): Connection layer for communication (serial, Bluetooth, etc.).
        tester_present_thread (threading.Thread | None): Thread for cyclic tester present.
        tester_present_running (bool): Flag indicating if tester present is active.
    """

    def __init__(self, connection: Connection) -> None:
        """
        Initialize the ELM327 driver with a connection layer.

        The connection should be opened before passing it to ELM327, or you can use
        the async context manager pattern to ensure proper initialization.

        Args:
            connection (Connection): An instance of a Connection implementation (SerialConnection,
                                     BluetoothConnection, etc.). The connection will be used for
                                     all communication with the ELM327 device.

        Example:
            >>> from driver.serial_connection import SerialConnection
            >>> async with SerialConnection('/dev/ttyUSB0') as conn:
            ...     elm = ELM327(conn)
            ...     await elm.initialize()
            ...     response = await elm.send_message(None, 0x0D)
        """
        self.connection = connection
        self.tester_present_thread: Optional[threading.Thread] = None
        self.tester_present_running: bool = False
        self._tester_present_interval: float = 2.0
        self._initialized: bool = False

    def initialize(self) -> None:
        """
        Initialize the ELM327 device with optimal settings.

        Configures the ELM327 adapter for OBD-II/UDS communication. This should be called
        once after the transport is opened.

        Raises:
            ConnectionException: If initialization fails.
        """
        try:
            # Reset and wait for initialization
            self._send_command('ATZ')
            if self.connection.needs_delays:
                time.sleep(1.0)
            
            # Configure ELM327
            self._send_command('ATE0')  # Echo off
            self._send_command('ATL0')  # Linefeeds off
            self._send_command('ATS0')  # Spaces off
            self._send_command('ATH1')  # Headers on
            self._send_command('ATSP0')  # Auto protocol detection
            
            self._initialized = True
        except ConnectionException as e:
            raise ELM327ConnectionException(f"Failed to initialize ELM327: {e}")

    def _send_command(self, command: str) -> str:
        """
        Send a command to the ELM327 device and read response.

        Args:
            command (str): AT command to send to the ELM327.

        Returns:
            str: Response from the ELM327 device.

        Raises:
            NotConnectedException: If connection is not established.
            ConnectionException: If communication fails.
        """
        try:
            # Send command with carriage return
            self.connection.write((command + '\r').encode('ascii'))
            
            # Brief pause for ELM327 to process (skip for mock/fast connections)
            if self.connection.needs_delays:
                time.sleep(0.1)
            
            # Read response
            response = self.connection.read(1024)
            return response.decode('ascii', errors='ignore').strip()
        except ConnectionException as e:
            raise NotConnectedException(f"Connection communication failed: {e}")

    def send_message(self, can_id: int | None, pid: int) -> IsoTpResponse:
        """
        Send an OBD-II or UDS message and receive the response.

        If can_id is specified, sends a UDS message to the specified CAN ID.
        Otherwise, sends a standard OBD-II request. For ISO-TP multi-frame messages,
        the complete payload is reassembled and returned as a structured response.

        Args:
            can_id (int | None): CAN identifier for UDS messages, or None for standard OBD-II.
            pid (int): Parameter ID (PID) for OBD-II or service ID for UDS.

        Returns:
            IsoTpResponse: Parsed response with service ID, data identifier, and payload.

        Raises:
            NotConnectedException: If connection is not established or not initialized.
            NoResponseException: If ECU or ELM327 does not respond or returns an error.
        """
        if not self._initialized:
            raise NotConnectedException("ELM327 not initialized. Call initialize() first.")

        # Construct message
        if can_id is not None:
            # UDS message with specific CAN ID
            header = f"ATSH{can_id:03X}"
            self._send_command(header)
            message = f"{pid:02X}"
        else:
            # Standard OBD-II request (Mode 01)
            message = f"01{pid:02X}"

        # Send message
        response_str = self._send_command(message)
        
        # Check for various ELM327 status/error messages that aren't actual data
        error_keywords = [
            'NO DATA',      # ECU not responding
            'ERROR',        # General error
            '?',            # Unknown command
            'STOPPED',      # Data stream stopped
            'UNABLE TO CONNECT',  # Cannot connect to ECU
            'BUS INIT',     # Bus initialization message
            'CAN ERROR',    # CAN bus error
            'BUFFER FULL',  # Internal buffer overflow
            '<DATA ERROR', # Data transmission error
        ]
        
        for keyword in error_keywords:
            if keyword in response_str:
                raise NoResponseException(f"ELM327 error or status message: {response_str}")
        
        # Parse response and handle ISO-TP multi-frame if needed
        raw_payload = self._parse_response(response_str)
        
        # Parse UDS response into structured format
        return parse_uds_response(raw_payload)

    def _parse_response(self, response: str) -> bytearray:
        """
        Parse ELM327 response and extract ISO-TP frames.

        Args:
            response (str): Raw response string from ELM327.

        Returns:
            bytearray: Parsed response data.

        Raises:
            InvalidResponseException: If response format is invalid or cannot be parsed.
        """
        # Remove prompt
        response = response.replace('>', '')
        
        # Remove common ELM327 informational messages that may appear in responses
        informational_messages = [
            'SEARCHING...',
            'BUSINIT:',
            'BUSINIT...',
            'OK',
        ]
        
        for msg in informational_messages:
            response = response.replace(msg, '')
        
        # Split by line breaks to process each CAN frame separately
        # This handles both formats: with spaces (7EC 10 3E...) and without (7EC103E...)
        lines = response.replace('\r\r', '\r').replace('\n\n', '\n').split('\r')
        if not lines or len(lines) == 1:
            lines = response.split('\n')
        
        frame_data_list: list[str] = []
        can_id_length = 3
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove spaces from this line to normalize format
            line_no_spaces = line.replace(' ', '')
            
            # Check if line starts with a valid CAN ID (3 hex chars)
            if len(line_no_spaces) >= can_id_length:
                try:
                    potential_id = line_no_spaces[:can_id_length]
                    int(potential_id, 16)  # Validate it's hex
                    
                    # Extract data after CAN ID (typically 8 bytes = 16 hex chars)
                    frame_data = line_no_spaces[can_id_length:]
                    if frame_data and len(frame_data) >= 2:  # At least 1 byte of data
                        frame_data_list.append(frame_data)
                except ValueError:
                    # Not a valid CAN frame, skip this line
                    continue
        
        # If no frames found, try to parse entire response as single hex string
        if not frame_data_list:
            response_clean = response.replace('\r', '').replace('\n', '').replace(' ', '')
            try:
                data = bytearray.fromhex(response_clean)
                return data
            except ValueError:
                raise InvalidResponseException(f"Invalid response format: {response}")
        
        # Use ISO-TP module to parse and reassemble frames
        try:
            payload = parse_isotp_frames(frame_data_list)
            return payload
        except ValueError as e:
            raise InvalidResponseException(f"ISO-TP parsing error: {e}")


    def enable_cyclic_tester_present(self, cycle_time: float = 2.0) -> None:
        """
        Enable cyclic transmission of UDS Tester Present message.

        Starts a background thread that periodically sends the Tester Present (0x3E)
        message to keep the ECU diagnostic session alive.

        Args:
            cycle_time (float): Interval between Tester Present messages in seconds (default: 2.0).
        """
        if self.tester_present_running:
            return
        
        self._tester_present_interval = cycle_time
        self.tester_present_running = True
        self.tester_present_thread = threading.Thread(target=self._tester_present_loop, daemon=True)
        self.tester_present_thread.start()

    def _tester_present_loop(self) -> None:
        """
        Background loop for sending cyclic Tester Present messages.

        This method runs in a separate thread and should not be called directly.
        Uses asyncio.run to execute async commands in the thread context.
        """
        while self.tester_present_running:
            try:
                # Send Tester Present (0x3E 0x00) - suppress positive response
                try:
                    self._send_command('3E00')
                except Exception:
                    pass
            except Exception:
                pass  # Ignore errors in background thread
            time.sleep(self._tester_present_interval)

    def disable_tester_present(self) -> None:
        """
        Disable cyclic Tester Present message transmission.

        Stops the background thread that sends Tester Present messages.
        """
        self.tester_present_running = False
        if self.tester_present_thread is not None:
            self.tester_present_thread.join(timeout=self._tester_present_interval + 1.0)
            self.tester_present_thread = None

    def close(self) -> None:
        """
        Close the connection and stop all background tasks.

        Should be called when the driver is no longer needed to free resources.
        """
        self.disable_tester_present()
        self.connection.close()
        self._initialized = False