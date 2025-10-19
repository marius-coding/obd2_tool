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
            '220101': 'SEARCHING...\r',
            '220102': 'SEARCHING...\r7EC1027620102FFFFFF\r7EC21FFBCBCBCBCBCBC\r7EC22BCBCBCBCBCBCBC\r7EC23BCBCBCBCBCBCBC\r7EC24BCBCBCBCBCBCBC\r7EC25BCBCBCBCBCAAAA\r\r>',
            '220105': '7EC102E620105FFFB74\r7EC210F012C01012C0B\r7EC220B0C0B0C0C0C3E\r7EC239043820000640E\r7EC240003E82139A000\r7EC2567000000000000\r7EC26000C0C0D0DAAAA\r\r>',
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
        
        # Handle special case: 220101 returns STOPPED on second call
        if command == '220101' and self.call_count[command] == 2:
            self.response_queue = ['STOPPED\r\r>']
        elif command in self.responses:
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
