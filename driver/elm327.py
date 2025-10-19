"""
ELM327 driver module for OBD-II communication.

This module provides an interface to communicate with ELM327-based OBD-II adapters.
"""

import serial  # type: ignore[import-untyped]
import serial.tools.list_ports  # type: ignore[import-untyped]
import threading
import time
from typing import Optional
from .isotp import IsoTpResponse 

from .exceptions import (
    ConnectionException,
    DeviceNotFoundException,
    InvalidResponseException,
    NoResponseException,
    NotConnectedException,
)
from .isotp import parse_isotp_frames, parse_uds_response, IsoTpResponse


class ELM327:
    """
    Driver for ELM327-based OBD-II adapters.

    This class handles serial communication with ELM327 devices, supporting both
    standard OBD-II requests and UDS (Unified Diagnostic Services) messages over
    ISO-TP protocol.

    Attributes:
        port (str | None): Serial port name or None for automatic detection.
        baudrate (int): Communication baudrate (default: 38400).
        timeout (float): Serial read timeout in seconds.
        serial_connection (Any): Active serial connection.
        tester_present_thread (threading.Thread | None): Thread for cyclic tester present.
        tester_present_running (bool): Flag indicating if tester present is active.
    """

    def __init__(self, port: str | None = None, baudrate: int = 38400, timeout: float = 1.0,
                 serial_connection: Optional[object] = None) -> None:
        """
        Initialize the ELM327 driver.

        If port is None, the driver will attempt to automatically detect and connect
        to an ELM327 device on available serial ports.

        Args:
            port (str | None): Serial port name (e.g., '/dev/ttyUSB0', 'COM3') or None for auto-detection.
            baudrate (int): Communication baudrate (default: 38400).
            timeout (float): Serial read timeout in seconds (default: 1.0).
            serial_connection (object | None): Optional mock serial connection for testing.
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection: Optional[object] = serial_connection
        self.tester_present_thread: Optional[threading.Thread] = None
        self.tester_present_running: bool = False
        self._tester_present_interval: float = 2.0

        if self.serial_connection is None:
            if self.port is None:
                self.port = self._auto_detect_port()
            
            self._connect()

    def _auto_detect_port(self) -> str:
        """
        Automatically detect ELM327 device on available serial ports.

        Searches through available serial ports and attempts to identify an ELM327 device
        by sending the ATZ (reset) command and checking for a valid response.

        Returns:
            str: The detected port name.

        Raises:
            DeviceNotFoundException: If no ELM327 device is found on any available port.
        """
        ports = serial.tools.list_ports.comports()
        
        for port_info in ports:
            try:
                test_serial = serial.Serial(port_info.device, self.baudrate, timeout=self.timeout)
                test_serial.write(b'ATZ\r')
                time.sleep(1)
                response = test_serial.read(100).decode('ascii', errors='ignore')
                test_serial.close()
                
                if 'ELM327' in response or 'ELM' in response:
                    return port_info.device
            except (serial.SerialException, OSError):
                continue
        
        raise DeviceNotFoundException("No ELM327 device found on available ports")

    def _connect(self) -> None:
        """
        Establish serial connection and initialize ELM327 device.

        Configures the ELM327 adapter with optimal settings for OBD-II/UDS communication.

        Raises:
            ConnectionException: If connection or initialization fails.
        """
        try:
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            time.sleep(0.1)
            
            # Initialize ELM327
            self._send_command('ATZ')  # Reset
            time.sleep(1)
            self._send_command('ATE0')  # Echo off
            self._send_command('ATL0')  # Linefeeds off
            self._send_command('ATS0')  # Spaces off
            self._send_command('ATH1')  # Headers on
            self._send_command('ATSP0')  # Auto protocol detection
        except serial.SerialException as e:
            raise ConnectionException(f"Failed to connect to ELM327 on {self.port}: {e}")

    def _send_command(self, command: str) -> str:
        """
        Send a command to the ELM327 device and read response.

        Args:
            command (str): AT command to send to the ELM327.

        Returns:
            str: Response from the ELM327 device.

        Raises:
            NotConnectedException: If no serial connection is established.
        """
        if self.serial_connection is None:
            raise NotConnectedException("No active serial connection")
        
        self.serial_connection.write((command + '\r').encode('ascii'))  # type: ignore[attr-defined]
        time.sleep(0.1)
        response = self.serial_connection.read(1024).decode('ascii', errors='ignore')  # type: ignore[attr-defined]
        return response.strip()  # type: ignore[return-value]

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
            NotConnectedException: If no serial connection is established.
            NoResponseException: If ECU or ELM327 does not respond or returns an error.
        """
        if self.serial_connection is None:
            raise NotConnectedException("No active serial connection")

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
        """
        while self.tester_present_running:
            try:
                # Send Tester Present (0x3E 0x00) - suppress positive response
                self._send_command('3E00')
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
        Close the serial connection and stop all background tasks.

        Should be called when the driver is no longer needed to free resources.
        """
        self.disable_tester_present()
        if self.serial_connection is not None:
            self.serial_connection.close()  # type: ignore[attr-defined]
            self.serial_connection = None