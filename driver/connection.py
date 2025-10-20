"""
Abstract connection interface for OBD2 communication.

This module provides base classes for different connection mechanisms
(Serial, Bluetooth, etc.) used to communicate with OBD2 adapters.
"""

from abc import ABC, abstractmethod
from typing import Optional


class Connection(ABC):
    """Abstract base class for OBD2 device connections."""

    def __init__(self) -> None:
        """Initialize the connection."""
        self._is_open: bool = False
        self._needs_delays: bool = True  # Override to False for mock/fast connections

    @abstractmethod
    def open(self) -> None:
        """
        Open the connection.

        Raises:
            ConnectionException: If connection fails
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close the connection.

        Raises:
            ConnectionException: If disconnection fails
        """
        pass

    @abstractmethod
    def write(self, data: bytes) -> None:
        """
        Write data to the connection.

        Args:
            data: Bytes to write

        Raises:
            ConnectionException: If write fails
        """
        pass

    @abstractmethod
    def read(self, size: int = 1) -> bytes:
        """
        Read data from the connection.

        Args:
            size: Number of bytes to read

        Returns:
            Bytes read from connection

        Raises:
            ConnectionException: If read fails
        """
        pass

    @abstractmethod
    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """
        Read data until a terminator is found.

        Args:
            terminator: Byte sequence to read until
            timeout: Optional timeout in seconds

        Returns:
            Bytes read including terminator

        Raises:
            ConnectionException: If read fails
            TimeoutError: If timeout is exceeded
        """
        pass

    @abstractmethod
    def flush_input(self) -> None:
        """
        Flush input buffer.

        Raises:
            ConnectionException: If flush fails
        """
        pass

    @abstractmethod
    def flush_output(self) -> None:
        """
        Flush output buffer.

        Raises:
            ConnectionException: If flush fails
        """
        pass

    @property
    def is_open(self) -> bool:
        """Check if connection is open."""
        return self._is_open

    @property
    def needs_delays(self) -> bool:
        """Check if connection needs delays between operations (False for mock/fast connections)."""
        return self._needs_delays

    def __enter__(self) -> "Connection":
        """Context manager entry."""
        # Synchronous context manager: open the connection on enter
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        try:
            self.close()
        except Exception:
            pass



class ConnectionException(Exception):
    """Base exception for connection errors."""
    pass


class ConnectionTimeoutError(ConnectionException):
    """Timeout during connection operation."""
    pass


class ConnectionError(ConnectionException):
    """Error during connection operation."""
    pass
