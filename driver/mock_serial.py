"""
Mock serial interface for testing ELM327 driver.

This module provides a mock serial connection that simulates ELM327 responses
based on recorded communication traces.
"""

from typing import Optional

from .connection import Connection


class MockConnection(Connection):
    """
    Mock connection for testing ELM327 communication.

    Simulates ELM327 device responses based on predefined command-response pairs.

    Attributes:
        responses (dict): Dictionary mapping commands to responses.
        response_queue (list): Queue of responses for multi-line responses.
        call_count (dict): Counter for command calls.
    """

    def __init__(self) -> None:
        """
        Initialize mock connection.
        """
        super().__init__()
        self._needs_delays = False  # Mock connections don't need delays
        self.response_queue: list[str] = []
        self.call_count: dict[str, int] = {}
        self._read_buffer: bytes = b''
        
        # Predefined responses based on recorded trace
        self.responses: dict[str, str] = {
            'ATZ': '\r\rELM327 v1.5\r\r>',
            'ATE0': 'ATE0\rOK\r\r>',
            'ATL0': 'OK\r\r>',
            'ATS0': 'OK\r\r>',
            'ATH1': 'OK\r\r>',
            'ATSP0': 'OK\r\r>',
            'ATSH7E4': 'OK\r\r>',
            # Real trace from Kia Niro EV showing SOC = 52.5%
            # Using realistic format with spaces between bytes
            '220101': '7EC 10 3E 62 01 01 EF FB E7 \r7EC 21 ED 69 00 00 00 00 00 \r7EC 22 00 00 0E 26 0D 0C 0D \r7EC 23 0D 0D 00 00 00 34 BC \r7EC 24 18 BC 56 00 00 7C 00 \r7EC 25 02 DE 80 00 02 C9 55 \r7EC 26 00 01 19 AF 00 01 07 \r7EC 27 C3 00 EC 65 6F 00 00 \r7EC 28 03 00 00 00 00 0B B8 \r\r>',
            '220102': 'SEARCHING...\r7EC 10 27 62 01 02 FF FF FF \r7EC 21 FF BC BC BC BC BC BC BC \r7EC 22 BC BC BC BC BC BC BC BC \r7EC 23 BC BC BC BC BC BC BC BC \r7EC 24 BC BC BC BC BC BC BC BC \r7EC 25 BC BC BC BC BC BC AA AA \r\r>',
            '220105': '7EC 10 2E 62 01 05 FF FF 0B 74 \r7EC 21 0F 01 2C 01 01 2C 0B \r7EC 22 0B 0C 0B 0C 0C 0C 3E \r7EC 23 90 43 82 00 00 64 0E \r7EC 24 00 03 E8 21 39 A0 00 \r7EC 25 67 00 00 00 00 00 00 \r7EC 26 00 0C 0C 0D 0D AA AA \r\r>',
        }

    def open(self) -> None:
        """
        Open the mock connection.
        """
        self._is_open = True

    def close(self) -> None:
        """
        Close the mock connection.
        """
        self._is_open = False
        self.response_queue.clear()
        self._read_buffer = b''

    def write(self, data: bytes) -> None:
        """
        Mock write operation.

        Args:
            data (bytes): Data to write.
        """
        command = data.decode('ascii').strip()
        
        # Track call count for commands that behave differently on repeated calls
        if command not in self.call_count:
            self.call_count[command] = 0
        self.call_count[command] += 1
        
        # Queue the appropriate response
        if command in self.responses:
            response = self.responses[command]
        else:
            response = '?\r\r>'
        
        # Add response to read buffer
        self._read_buffer += response.encode('ascii')

    def read(self, size: int = 1) -> bytes:
        """
        Mock read operation.

        Args:
            size (int): Maximum number of bytes to read.

        Returns:
            bytes: Response data.
        """
        # Read from buffer
        if len(self._read_buffer) <= size:
            result = self._read_buffer
            self._read_buffer = b''
        else:
            result = self._read_buffer[:size]
            self._read_buffer = self._read_buffer[size:]
        
        return result

    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """
        Read data until a terminator is found.

        Args:
            terminator: Byte sequence to read until
            timeout: Optional timeout in seconds (not used in mock)

        Returns:
            Bytes read including terminator
        """
        # Find terminator in buffer
        idx = self._read_buffer.find(terminator)
        if idx != -1:
            # Include terminator
            result = self._read_buffer[:idx + len(terminator)]
            self._read_buffer = self._read_buffer[idx + len(terminator):]
            return result
        
        # Return everything if no terminator found
        result = self._read_buffer
        self._read_buffer = b''
        return result

    def flush_input(self) -> None:
        """
        Flush input buffer.
        """
        self._read_buffer = b''

    def flush_output(self) -> None:
        """
        Flush output buffer (no-op for mock).
        """
        pass
