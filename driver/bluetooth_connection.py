"""
Bluetooth connection layer for OBD2 communication.

This module provides Bluetooth connectivity for OBD2 adapters using RFCOMM.
"""

import subprocess
import time
from pathlib import Path
from typing import Optional

import serial  # type: ignore[import-untyped]

from .connection import Connection, ConnectionError, ConnectionException, ConnectionTimeoutError


class BluetoothConnection(Connection):
    """Bluetooth RFCOMM connection for OBD2 communication."""

    def __init__(
        self,
        address: str,
        rfcomm_device: int = 0,
        channel: int = 1,
        baudrate: int = 115200,
        timeout: float = 1.0,
        write_timeout: float = 1.0,
        auto_bind: bool = True,
    ) -> None:
        """
        Initialize Bluetooth connection.

        Args:
            address: Bluetooth MAC address (e.g., '00:1D:A5:1E:32:25')
            rfcomm_device: RFCOMM device number (0 = /dev/rfcomm0)
            channel: RFCOMM channel (usually 1)
            baudrate: Baud rate for serial communication
            timeout: Read timeout in seconds
            write_timeout: Write timeout in seconds
            auto_bind: Automatically bind RFCOMM on open
        """
        super().__init__()
        self.address = address
        self.rfcomm_device = rfcomm_device
        self.channel = channel
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.auto_bind = auto_bind
        self._serial: Optional[serial.Serial] = None
        self._rfcomm_process: Optional[subprocess.Popen] = None

    @property
    def device_path(self) -> str:
        """Get the RFCOMM device path."""
        return f"/dev/rfcomm{self.rfcomm_device}"

    def _ensure_bluetoothctl_connected(self) -> None:
        """Ensure the Bluetooth device is connected via bluetoothctl."""
        try:
            # Check if already connected
            proc = subprocess.run(["bluetoothctl", "info", self.address], capture_output=True)
            stdout = proc.stdout

            if b"Connected: yes" in stdout:
                return  # Already connected

            # Try to connect
            subprocess.run(["bluetoothctl", "connect", self.address], capture_output=True, timeout=10.0)

            # Wait a moment for connection to stabilize
            time.sleep(0.5)

        except Exception:
            pass  # Not critical if bluetoothctl fails

    def _bind_rfcomm(self) -> None:
        """Bind the RFCOMM device."""
        try:
            # Check if already bound
            if Path(self.device_path).exists():
                # Try to release first
                self._release_rfcomm()
                time.sleep(0.2)

            # Bind the RFCOMM device
            proc = subprocess.Popen(["sudo", "rfcomm", "bind", str(self.rfcomm_device), self.address, str(self.channel)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = proc.communicate(timeout=5.0)

            if proc.returncode != 0 and b"busy" not in (stderr or b"").lower():
                raise ConnectionError(
                    f"Failed to bind RFCOMM device: {stderr.decode() if stderr else ''}"
                )

            # Wait for device to appear
            for _ in range(20):
                if Path(self.device_path).exists():
                    break
                time.sleep(0.1)
            else:
                raise ConnectionError(
                    f"RFCOMM device {self.device_path} did not appear"
                )

        except subprocess.TimeoutExpired as e:
            raise ConnectionError("Timeout binding RFCOMM device") from e
        except Exception as e:
            raise ConnectionError(f"Error binding RFCOMM device: {e}") from e

    def _release_rfcomm(self) -> None:
        """Release the RFCOMM device."""
        try:
            proc = subprocess.Popen(["sudo", "rfcomm", "release", str(self.rfcomm_device)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.communicate(timeout=2.0)
        except Exception:
            pass  # Ignore errors during release

    def open(self) -> None:
        """Open the Bluetooth connection."""
        if self._is_open:
            return

        try:
            # Ensure Bluetooth connection via bluetoothctl
            self._ensure_bluetoothctl_connected()

            if self.auto_bind:
                # Bind RFCOMM device
                self._bind_rfcomm()

            # Wait a moment for device to be ready
            time.sleep(0.3)

            # Open serial connection to RFCOMM device (synchronous)
            self._serial = serial.Serial(
                port=self.device_path,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.write_timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            self._is_open = True
        except serial.SerialException as e:
            self._release_rfcomm()
            raise ConnectionError(
                f"Failed to open Bluetooth device {self.address}: {e}"
            ) from e
        except Exception as e:
            self._release_rfcomm()
            raise ConnectionException(f"Unexpected error opening Bluetooth: {e}") from e

    def close(self) -> None:
        """Close the Bluetooth connection."""
        if not self._is_open:
            return

        try:
            # Close serial connection
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:
                    pass
                self._serial = None

            # Release RFCOMM binding
            if self.auto_bind:
                self._release_rfcomm()

            self._is_open = False

        except Exception as e:
            raise ConnectionException(f"Error closing Bluetooth connection: {e}") from e

    def write(self, data: bytes) -> None:
        """Write data to the Bluetooth device."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            self._serial.write(data)

        except serial.SerialTimeoutException as e:
            raise ConnectionTimeoutError(f"Write timeout: {e}") from e
        except serial.SerialException as e:
            raise ConnectionException(f"Bluetooth write error: {e}") from e

    def read(self, size: int = 1) -> bytes:
        """Read data from the Bluetooth device."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            data = self._serial.read(size)
            return data

        except serial.SerialException as e:
            raise ConnectionException(f"Bluetooth read error: {e}") from e

    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """Read data until a terminator is found."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        original_timeout = self._serial.timeout if self._serial else None
        try:
            if timeout is not None and self._serial:
                self._serial.timeout = timeout

            data = self._serial.read_until(terminator)
            return data

        except serial.SerialException as e:
            if "until" in str(e).lower() and "timeout" in str(e).lower():
                raise ConnectionTimeoutError(f"Read until timeout: {e}") from e
            raise ConnectionException(f"Bluetooth read error: {e}") from e
        finally:
            if original_timeout is not None and self._serial:
                self._serial.timeout = original_timeout

    def flush_input(self) -> None:
        """Flush input buffer."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            self._serial.reset_input_buffer()

        except serial.SerialException as e:
            raise ConnectionException(f"Error flushing input buffer: {e}") from e

    def flush_output(self) -> None:
        """Flush output buffer."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            self._serial.flush()

        except serial.SerialException as e:
            raise ConnectionException(f"Error flushing output buffer: {e}") from e

    @staticmethod
    def discover_devices(timeout: float = 5.0) -> list[dict[str, str]]:
        """
        Discover nearby Bluetooth devices.

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of discovered devices with 'address' and 'name' keys
        """
        devices = []
        try:
            proc = subprocess.Popen(["bluetoothctl", "scan", "on"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Let scan run for specified timeout
            time.sleep(timeout)

            # Stop scan
            proc.terminate()
            proc.wait()

            # Get discovered devices
            proc = subprocess.run(["bluetoothctl", "devices"], capture_output=True)
            stdout = proc.stdout

            # Parse output
            for line in stdout.decode().split("\n"):
                if line.startswith("Device "):
                    parts = line.split(maxsplit=2)
                    if len(parts) >= 3:
                        devices.append({
                            "address": parts[1],
                            "name": parts[2],
                        })

        except Exception:
            pass  # Return empty list on error

        return devices

    def __repr__(self) -> str:
        """String representation."""
        status = "open" if self._is_open else "closed"
        return (
            f"BluetoothTransport(address={self.address}, "
            f"device={self.device_path}, status={status})"
        )
