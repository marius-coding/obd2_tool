"""
Bluetooth connection layer for OBD2 communication.

This module provides Bluetooth connectivity for OBD2 adapters using RFCOMM.
run sudo rfcomm bind 0 00:1D:A5:1E:32:25 1
(substitute actual address)
"""

import socket
from typing import Optional

from .connection import Connection, ConnectionError, ConnectionException, ConnectionTimeoutError

# Bluetooth constants (may not be available on all systems)
AF_BLUETOOTH = getattr(socket, 'AF_BLUETOOTH', 31)
BTPROTO_RFCOMM = getattr(socket, 'BTPROTO_RFCOMM', 3)

# D-Bus imports for device connection
try:
    import dbus_fast as dbus
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False


class BluetoothConnection(Connection):
    """Bluetooth RFCOMM connection for OBD2 communication."""

    def __init__(
        self,
        address: str,
        channel: int = 1,
        timeout: float = 10.0,  # Increased for connection
    ) -> None:
        """
        Initialize Bluetooth connection.

        Args:
            address: Bluetooth MAC address (e.g., '00:1D:A5:1E:32:25')
            channel: RFCOMM channel (usually 1)
            timeout: Read/write timeout in seconds
        """
        super().__init__()
        self.address = address
        self.channel = channel
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None

    def _connect_device(self) -> None:
        """Connect to the Bluetooth device using D-Bus if available."""
        if not DBUS_AVAILABLE:
            return  # Skip if D-Bus not available
        
        try:
            # Connect to system bus
            bus = dbus.SystemBus()
            
            # Get the device object
            device_path = f"/org/bluez/hci0/dev_{self.address.replace(':', '_')}"
            device = bus.get_proxy_object('org.bluez', device_path)
            device_interface = device.get_interface('org.bluez.Device')
            
            # Check if already connected
            connected = device_interface.get_connected()
            if not connected:
                # Connect the device
                device_interface.call_connect()
                # Wait a bit for connection
                import time
                time.sleep(1.0)
                
        except Exception:
            # Ignore errors, socket connect will fail if device not connected
            pass

    def open(self) -> None:
        """Open the Bluetooth connection."""
        if self._is_open:
            return

        if not hasattr(socket, 'AF_BLUETOOTH'):
            raise ConnectionError("Bluetooth not supported on this system (missing AF_BLUETOOTH)")

        try:
            # First, ensure the device is connected at Bluetooth level
            self._connect_device()
            
            # Create RFCOMM socket
            self._socket = socket.socket(AF_BLUETOOTH, socket.SOCK_STREAM, BTPROTO_RFCOMM)
            
            # Set timeout for connection (longer)
            self._socket.settimeout(10.0)
            
            # Connect to the device
            self._socket.connect((self.address, self.channel))
            
            # Set timeout for read/write (shorter)
            self._socket.settimeout(self.timeout)
            
            self._is_open = True
        except OSError as e:
            raise ConnectionError(f"Failed to connect to {self.address}: {e}") from e

    def close(self) -> None:
        """Close the Bluetooth connection."""
        if not self._is_open:
            return

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self._is_open = False

    def write(self, data: bytes) -> None:
        """Write data to the Bluetooth device."""
        if not self._is_open or self._socket is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            self._socket.send(data)
        except OSError as e:
            raise ConnectionException(f"Bluetooth write error: {e}") from e

    def read(self, size: int = 1) -> bytes:
        """Read data from the Bluetooth device."""
        if not self._is_open or self._socket is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            data = self._socket.recv(size)
            return data
        except OSError as e:
            raise ConnectionException(f"Bluetooth read error: {e}") from e

    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """Read data until a terminator is found."""
        if not self._is_open or self._socket is None:
            raise ConnectionException("Bluetooth device not open")

        original_timeout = self._socket.gettimeout()
        try:
            if timeout is not None:
                self._socket.settimeout(timeout)

            data = b""
            while not data.endswith(terminator):
                chunk = self._socket.recv(1)
                if not chunk:
                    break
                data += chunk
            return data
        except OSError as e:
            if "timeout" in str(e).lower():
                raise ConnectionTimeoutError(f"Read until timeout: {e}") from e
            raise ConnectionException(f"Bluetooth read error: {e}") from e
        finally:
            self._socket.settimeout(original_timeout)

    def flush_input(self) -> None:
        """Flush input buffer."""
        # Bluetooth sockets don't have a direct flush, but we can read until empty
        if not self._is_open or self._socket is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            self._socket.settimeout(0.1)  # Short timeout for flush
            while True:
                try:
                    self._socket.recv(1024)
                except OSError:
                    break
        except OSError:
            pass
        finally:
            self._socket.settimeout(self.timeout)

    def flush_output(self) -> None:
        """Flush output buffer."""
        # Bluetooth sockets don't have output buffer flush
        pass

    @staticmethod
    def discover_devices(timeout: float = 5.0) -> list[dict[str, str]]:
        """
        Discover nearby Bluetooth devices.

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of discovered devices with 'address' and 'name' keys
        """
        raise NotImplementedError("Device discovery requires system Bluetooth tools or additional libraries")

    def __repr__(self) -> str:
        """String representation."""
        status = "open" if self._is_open else "closed"
        return (
            f"BluetoothConnection(address={self.address}, "
            f"channel={self.channel}, status={status})"
        )
