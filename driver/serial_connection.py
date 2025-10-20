"""
Serial connection layer for OBD2 communication.

This module provides serial port connectivity for OBD2 adapters.
"""

import asyncio
from typing import Optional

import serial
import serial.tools.list_ports

from .connection import Connection, ConnectionError, ConnectionException, ConnectionTimeoutError


class SerialConnection(Connection):
    """Serial port connection for OBD2 communication."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 1.0,
        write_timeout: float = 1.0,
    ) -> None:
        """
        Initialize serial connection.

        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0', 'COM3')
            baudrate: Baud rate for serial communication
            timeout: Read timeout in seconds
            write_timeout: Write timeout in seconds
        """
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self._serial: Optional[serial.Serial] = None

    async def open(self) -> None:
        """Open the serial port connection."""
        if self._is_open:
            return

        try:
            # Run blocking serial open in thread pool
            loop = asyncio.get_event_loop()
            self._serial = await loop.run_in_executor(
                None,
                lambda: serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=self.write_timeout,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                ),
            )
            self._is_open = True

        except serial.SerialException as e:
            raise ConnectionError(f"Failed to open serial port {self.port}: {e}") from e
        except Exception as e:
            raise ConnectionException(f"Unexpected error opening serial port: {e}") from e

    async def close(self) -> None:
        """Close the serial port connection."""
        if not self._is_open or self._serial is None:
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._serial.close)
            self._serial = None
            self._is_open = False

        except Exception as e:
            raise ConnectionException(f"Error closing serial port: {e}") from e

    async def write(self, data: bytes) -> None:
        """Write data to the serial port."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Serial port not open")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._serial.write, data)

        except serial.SerialTimeoutException as e:
            raise ConnectionTimeoutError(f"Write timeout: {e}") from e
        except serial.SerialException as e:
            raise ConnectionException(f"Serial write error: {e}") from e

    async def read(self, size: int = 1) -> bytes:
        """Read data from the serial port."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Serial port not open")

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._serial.read, size)
            return data

        except serial.SerialException as e:
            raise ConnectionException(f"Serial read error: {e}") from e

    async def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """Read data until a terminator is found."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Serial port not open")

        original_timeout = self._serial.timeout if self._serial else None
        try:
            if timeout is not None and self._serial:
                self._serial.timeout = timeout

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._serial.read_until, terminator)
            return data

        except serial.SerialException as e:
            if "until" in str(e).lower() and "timeout" in str(e).lower():
                raise ConnectionTimeoutError(f"Read until timeout: {e}") from e
            raise ConnectionException(f"Serial read error: {e}") from e
        finally:
            if original_timeout is not None and self._serial:
                self._serial.timeout = original_timeout

    async def flush_input(self) -> None:
        """Flush input buffer."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Serial port not open")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._serial.reset_input_buffer)

        except serial.SerialException as e:
            raise ConnectionException(f"Error flushing input buffer: {e}") from e

    async def flush_output(self) -> None:
        """Flush output buffer."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Serial port not open")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._serial.flush)

        except serial.SerialException as e:
            raise ConnectionException(f"Error flushing output buffer: {e}") from e

    @staticmethod
    def list_ports() -> list[str]:
        """
        List available serial ports.

        Returns:
            List of available serial port paths
        """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def __repr__(self) -> str:
        """String representation."""
        status = "open" if self._is_open else "closed"
        return f"SerialTransport(port={self.port}, baudrate={self.baudrate}, status={status})"
