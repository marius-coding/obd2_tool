"""
Mock serial interface for testing ELM327 driver.

This module provides a mock serial connection that simulates ELM327 responses
based on recorded communication traces.
"""


class MockSerial:
    """
    Mock serial connection for testing ELM327 communication.

    Simulates ELM327 device responses based on predefined command-response pairs.

    Attributes:
        port (str): The port name (not used in mock).
        baudrate (int): The baudrate (not used in mock).
        timeout (float): The timeout value (not used in mock).
        responses (dict): Dictionary mapping commands to responses.
        response_queue (list): Queue of responses for multi-line responses.
    """

    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        """
        Initialize mock serial connection.

        Args:
            port (str): The port name (not used in mock).
            baudrate (int): The baudrate (not used in mock).
            timeout (float): The timeout value (not used in mock).
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_open = True
        self.response_queue: list[str] = []
        self.call_count: dict[str, int] = {}
        
        # Predefined responses based on recorded trace
        self.responses = {
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
        self.call_count = {}

    def write(self, data: bytes) -> int:
        """
        Mock write operation.

        Args:
            data (bytes): Data to write.

        Returns:
            int: Number of bytes written.
        """
        command = data.decode('ascii').strip()
        
        # Track call count for commands that behave differently on repeated calls
        if command not in self.call_count:
            self.call_count[command] = 0
        self.call_count[command] += 1
        
        # Always return the same response for consistency in demo mode
        if command in self.responses:
            self.response_queue = [self.responses[command]]
        else:
            self.response_queue = ['?\r\r>']
        
        return len(data)

    def read(self, size: int) -> bytes:
        """
        Mock read operation.

        Args:
            size (int): Maximum number of bytes to read.

        Returns:
            bytes: Response data.
        """
        if self.response_queue:
            response = self.response_queue.pop(0)
            return response.encode('ascii')
        return b''

    def close(self) -> None:
        """
        Mock close operation.
        """
        self.is_open = False
