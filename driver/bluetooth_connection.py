"""
Bluetooth connection layer for OBD2 communication.

This module provides Bluetooth connectivity for OBD2 adapters using RFCOMM.
"""

import asyncio
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
        self._rfcomm_process: Optional[asyncio.subprocess.Process] = None

    @property
    def device_path(self) -> str:
        """Get the RFCOMM device path."""
        return f"/dev/rfcomm{self.rfcomm_device}"

    async def _ensure_bluetoothctl_connected(self) -> None:
        """Ensure the Bluetooth device is connected via bluetoothctl."""
        try:
            # Check if already connected
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "info", self.address,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            
            if b"Connected: yes" in stdout:
                return  # Already connected
            
            # Try to connect
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "connect", self.address,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=10.0)
            
            # Wait a moment for connection to stabilize
            await asyncio.sleep(0.5)
            
        except asyncio.TimeoutError:
            pass  # Connection may already exist
        except Exception:
            pass  # Not critical if bluetoothctl fails

    async def _bind_rfcomm(self) -> None:
        """Bind the RFCOMM device."""
        try:
            # Check if already bound
            if Path(self.device_path).exists():
                # Try to release first
                await self._release_rfcomm()
                await asyncio.sleep(0.2)

            # Bind the RFCOMM device
            proc = await asyncio.create_subprocess_exec(
                "sudo", "rfcomm", "bind",
                str(self.rfcomm_device),
                self.address,
                str(self.channel),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            
            if proc.returncode != 0 and b"busy" not in stderr.lower():
                raise ConnectionError(
                    f"Failed to bind RFCOMM device: {stderr.decode()}"
                )

            # Wait for device to appear
            for _ in range(20):
                if Path(self.device_path).exists():
                    break
                await asyncio.sleep(0.1)
            else:
                raise ConnectionError(
                    f"RFCOMM device {self.device_path} did not appear"
                )

        except asyncio.TimeoutError as e:
            raise ConnectionError("Timeout binding RFCOMM device") from e
        except Exception as e:
            raise ConnectionError(f"Error binding RFCOMM device: {e}") from e

    async def _release_rfcomm(self) -> None:
        """Release the RFCOMM device."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "sudo", "rfcomm", "release", str(self.rfcomm_device),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=2.0)
        except Exception:
            pass  # Ignore errors during release

    async def open(self) -> None:
        """Open the Bluetooth connection."""
        if self._is_open:
            return

        try:
            # Ensure Bluetooth connection via bluetoothctl
            await self._ensure_bluetoothctl_connected()

            if self.auto_bind:
                # Bind RFCOMM device
                await self._bind_rfcomm()
            
            # Wait a moment for device to be ready
            await asyncio.sleep(0.3)

            # Open serial connection to RFCOMM device
            loop = asyncio.get_event_loop()
            self._serial = await loop.run_in_executor(
                None,
                lambda: serial.Serial(
                    port=self.device_path,
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
            await self._release_rfcomm()
            raise ConnectionError(
                f"Failed to open Bluetooth device {self.address}: {e}"
            ) from e
        except Exception as e:
            await self._release_rfcomm()
            raise ConnectionException(f"Unexpected error opening Bluetooth: {e}") from e

    async def close(self) -> None:
        """Close the Bluetooth connection."""
        if not self._is_open:
            return

        try:
            # Close serial connection
            if self._serial is not None:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._serial.close)
                self._serial = None

            # Release RFCOMM binding
            if self.auto_bind:
                await self._release_rfcomm()

            self._is_open = False

        except Exception as e:
            raise ConnectionException(f"Error closing Bluetooth connection: {e}") from e

    async def write(self, data: bytes) -> None:
        """Write data to the Bluetooth device."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._serial.write, data)

        except serial.SerialTimeoutException as e:
            raise ConnectionTimeoutError(f"Write timeout: {e}") from e
        except serial.SerialException as e:
            raise ConnectionException(f"Bluetooth write error: {e}") from e

    async def read(self, size: int = 1) -> bytes:
        """Read data from the Bluetooth device."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._serial.read, size)
            return data

        except serial.SerialException as e:
            raise ConnectionException(f"Bluetooth read error: {e}") from e

    async def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """Read data until a terminator is found."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

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
            raise ConnectionException(f"Bluetooth read error: {e}") from e
        finally:
            if original_timeout is not None and self._serial:
                self._serial.timeout = original_timeout

    async def flush_input(self) -> None:
        """Flush input buffer."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._serial.reset_input_buffer)

        except serial.SerialException as e:
            raise ConnectionException(f"Error flushing input buffer: {e}") from e

    async def flush_output(self) -> None:
        """Flush output buffer."""
        if not self._is_open or self._serial is None:
            raise ConnectionException("Bluetooth device not open")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._serial.flush)

        except serial.SerialException as e:
            raise ConnectionException(f"Error flushing output buffer: {e}") from e

    @staticmethod
    async def discover_devices(timeout: float = 5.0) -> list[dict[str, str]]:
        """
        Discover nearby Bluetooth devices.

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of discovered devices with 'address' and 'name' keys
        """
        devices = []
        try:
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "scan", "on",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Let scan run for specified timeout
            await asyncio.sleep(timeout)

            # Stop scan
            proc.terminate()
            await proc.wait()

            # Get discovered devices
            proc = await asyncio.create_subprocess_exec(
                "bluetoothctl", "devices",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

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
