"""
BLE (Bluetooth Low Energy) connection layer for OBD2 communication.

This module provides BLE connectivity for OBD2 adapters like the Vgate iCar Pro.
Supports ELM327-compatible BLE dongles.

Note: This uses bleak which requires asyncio internally, but we wrap it
to provide a synchronous interface using a background thread.
"""

import asyncio
import threading
import time
from typing import Optional, Any

try:
    from bleak import BleakClient, BleakScanner
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False

from .connection import Connection, ConnectionError, ConnectionException, ConnectionTimeoutError


class BLEConnection(Connection):
    """BLE connection for OBD2 communication using Bleak with synchronous interface."""

    # Common service UUIDs for OBD2 BLE adapters
    COMMON_SERVICE_UUIDS = [
        "0000fff0-0000-1000-8000-00805f9b34fb",  # Standard ELM327 BLE
        "e7810a71-73ae-499d-8c15-faa9aef0c3f2",  # Vgate iCar Pro / IOS-Vlink
    ]

    def __init__(
        self,
        address: str,
        timeout: float = 10.0,
        service_uuid: Optional[str] = None,
        notify_uuid: Optional[str] = None,
        write_uuid: Optional[str] = None,
    ) -> None:
        """
        Initialize BLE connection.

        Args:
            address: BLE device address (e.g., 'D2:E0:2F:8D:5C:6B')
            timeout: Connection and read/write timeout in seconds
            service_uuid: Optional specific service UUID to use
            notify_uuid: Optional specific notify characteristic UUID
            write_uuid: Optional specific write characteristic UUID
        """
        super().__init__()
        
        if not BLEAK_AVAILABLE:
            raise ConnectionError("bleak library not available. Install with: pip install bleak")
        
        self.address = address
        self.timeout = timeout
        self._service_uuid = service_uuid
        self._notify_uuid = notify_uuid
        self._write_uuid = write_uuid
        self._read_buffer = bytearray()
        self._buffer_lock = threading.Lock()
        self._client: Optional[Any] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_ready = threading.Event()
        self._debug = False  # Enable debug printing for sent/received data

    def _notification_handler(self, sender: Any, data: bytearray) -> None:
        """Handle incoming BLE notifications."""
        if self._debug:
            # Print received data in real-time with hex and ASCII
            ascii_repr = data.decode('ascii', errors='replace').replace('\r', '\\r').replace('\n', '\\n')
            hex_repr = ' '.join(f'{b:02X}' for b in data)
            print(f"\n[BLE RX {len(data):3d}B] {ascii_repr}")
            print(f"         HEX: {hex_repr}")
        
        with self._buffer_lock:
            self._read_buffer.extend(data)

    def _run_event_loop(self) -> None:
        """Run the asyncio event loop in a background thread."""
        self._event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._event_loop)
        self._loop_ready.set()
        self._event_loop.run_forever()

    def _ensure_event_loop(self) -> None:
        """Ensure the event loop is running in a background thread."""
        if self._loop_thread is None or not self._loop_thread.is_alive():
            self._loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._loop_thread.start()
            self._loop_ready.wait(timeout=2.0)

    def _run_coroutine(self, coro: Any) -> Any:
        """Run a coroutine in the background event loop and wait for result."""
        self._ensure_event_loop()
        if self._event_loop is None:
            raise ConnectionException("Event loop not initialized")
        
        future = asyncio.run_coroutine_threadsafe(coro, self._event_loop)
        try:
            return future.result(timeout=self.timeout)
        except Exception as e:
            raise ConnectionException(f"BLE operation failed: {e}") from e

    async def _discover_characteristics(self) -> None:
        """Discover write and notify characteristics."""
        if not self._client or not self._client.is_connected:
            raise ConnectionException("BLE client not connected")

        # If UUIDs are already specified, validate them
        if self._notify_uuid and self._write_uuid:
            return

        # Find characteristics
        notify_char = None
        write_char = None

        for service in self._client.services:
            # If service UUID specified, only look in that service
            if self._service_uuid and service.uuid.lower() != self._service_uuid.lower():
                continue

            for char in service.characteristics:
                # Look for notify characteristic
                if "notify" in char.properties or "indicate" in char.properties:
                    if not self._notify_uuid:
                        self._notify_uuid = char.uuid
                        notify_char = char

                # Look for write characteristic
                if "write" in char.properties or "write-without-response" in char.properties:
                    if not self._write_uuid:
                        self._write_uuid = char.uuid
                        write_char = char

                # Some characteristics support both read and write
                if notify_char and write_char:
                    break

            if notify_char and write_char:
                break

        if not self._notify_uuid:
            raise ConnectionError("No notify characteristic found")
        if not self._write_uuid:
            raise ConnectionError("No write characteristic found")

    async def _open_async(self) -> None:
        """Open the BLE connection (async)."""
        if self._is_open:
            return

        try:
            # Create BLE client
            self._client = BleakClient(self.address, timeout=self.timeout)

            # Connect
            await self._client.connect()

            if not self._client.is_connected:
                raise ConnectionError(f"Failed to connect to {self.address}")

            # Discover characteristics
            await self._discover_characteristics()

            # Start notifications
            if self._notify_uuid:
                await self._client.start_notify(self._notify_uuid, self._notification_handler)

            self._is_open = True

        except Exception as e:
            if self._client:
                try:
                    await self._client.disconnect()
                except:
                    pass
                self._client = None
            raise ConnectionError(f"Failed to open BLE connection: {e}") from e

    def open(self) -> None:
        """Open the BLE connection."""
        if self._is_open:
            return

        try:
            self._run_coroutine(self._open_async())
        except Exception as e:
            raise ConnectionError(f"Failed to open BLE connection: {e}") from e

    async def _close_async(self) -> None:
        """Close the BLE connection (async)."""
        if not self._is_open:
            return

        if self._client:
            try:
                # Stop notifications
                if self._notify_uuid:
                    await self._client.stop_notify(self._notify_uuid)
            except:
                pass

            try:
                await self._client.disconnect()
            except:
                pass

            self._client = None

        self._is_open = False

    def close(self) -> None:
        """Close the BLE connection."""
        if not self._is_open:
            return

        try:
            self._run_coroutine(self._close_async())
        except:
            pass

        # Stop event loop
        if self._event_loop:
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            self._event_loop = None

        self._is_open = False

    async def _write_async(self, data: bytes) -> None:
        """Write data to the BLE device (async)."""
        if not self._is_open or not self._client:
            raise ConnectionException("BLE device not open")

        if not self._write_uuid:
            raise ConnectionException("Write characteristic not found")

        try:
            await self._client.write_gatt_char(self._write_uuid, data)
        except Exception as e:
            raise ConnectionException(f"BLE write error: {e}") from e

    def write(self, data: bytes) -> None:
        """Write data to the BLE device."""
        if not self._is_open or not self._client:
            raise ConnectionException("BLE device not open")

        if self._debug:
            # Print sent data in real-time with hex and ASCII
            ascii_repr = data.decode('ascii', errors='replace').replace('\r', '\\r').replace('\n', '\\n')
            hex_repr = ' '.join(f'{b:02X}' for b in data)
            print(f"\n[BLE TX {len(data):3d}B] {ascii_repr}")
            print(f"         HEX: {hex_repr}")

        self._run_coroutine(self._write_async(data))

    def read(self, size: int = 1) -> bytes:
        """
        Read data from the BLE device.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Bytes read from the device
        """
        if not self._is_open:
            raise ConnectionException("BLE device not open")

        start_time = time.time()
        
        # Wait for data to arrive in buffer
        while True:
            with self._buffer_lock:
                if len(self._read_buffer) >= size:
                    # Extract data
                    data = bytes(self._read_buffer[:size])
                    self._read_buffer = self._read_buffer[size:]
                    return data
            
            # Check timeout
            if time.time() - start_time >= self.timeout:
                raise ConnectionTimeoutError("BLE read timeout")
            
            # Small sleep to avoid busy waiting
            time.sleep(0.01)

    def read_until(self, terminator: bytes, timeout: Optional[float] = None) -> bytes:
        """
        Read data until a terminator is found.
        
        Args:
            terminator: Byte sequence to read until
            timeout: Optional timeout override
            
        Returns:
            Bytes read including the terminator
        """
        if not self._is_open:
            raise ConnectionException("BLE device not open")

        read_timeout = timeout if timeout is not None else self.timeout
        start_time = time.time()

        while True:
            with self._buffer_lock:
                # Check if terminator is in buffer
                if terminator in self._read_buffer:
                    # Find position and extract data
                    pos = self._read_buffer.find(terminator)
                    data = bytes(self._read_buffer[: pos + len(terminator)])
                    self._read_buffer = self._read_buffer[pos + len(terminator) :]
                    return data

            # Check timeout
            if time.time() - start_time >= read_timeout:
                raise ConnectionTimeoutError("BLE read_until timeout")

            # Small sleep to avoid busy waiting
            time.sleep(0.01)

    def flush_input(self) -> None:
        """Flush input buffer."""
        with self._buffer_lock:
            self._read_buffer.clear()

    def flush_output(self) -> None:
        """Flush output buffer (no-op for BLE)."""
        pass

    @staticmethod
    def discover_devices(timeout: float = 10.0, name_filter: Optional[str] = None) -> list[dict[str, str]]:
        """
        Discover nearby BLE devices.

        Args:
            timeout: Scan timeout in seconds
            name_filter: Optional filter to match device names (case-insensitive)

        Returns:
            List of discovered BLE devices with 'name' and 'address' keys
        """
        if not BLEAK_AVAILABLE:
            raise ConnectionError("bleak library not available. Install with: pip install bleak")

        async def _discover() -> list[dict[str, str]]:
            devices = await BleakScanner.discover(timeout=timeout)
            
            result = []
            for device in devices:
                name = device.name or "Unknown"
                address = device.address
                
                # Apply name filter if specified
                if name_filter and name_filter.lower() not in name.lower():
                    continue
                
                result.append({"name": name, "address": address})
            
            return result

        # Run in a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_discover())
        finally:
            loop.close()

    @staticmethod
    def discover_obd_devices(timeout: float = 10.0) -> list[dict[str, str]]:
        """
        Discover OBD2 BLE devices.

        Args:
            timeout: Scan timeout in seconds

        Returns:
            List of potential OBD2 BLE devices with 'name' and 'address' keys
        """
        if not BLEAK_AVAILABLE:
            raise ConnectionError("bleak library not available. Install with: pip install bleak")

        async def _discover() -> list[dict[str, str]]:
            devices = await BleakScanner.discover(timeout=timeout)
            
            # Common OBD2 device name patterns
            obd_patterns = ["vgate", "vlink", "obd", "elm", "icar", "v-link", "ios-vlink"]
            
            result = []
            for device in devices:
                name = device.name or "Unknown"
                address = device.address
                
                # Check if name matches OBD2 patterns
                if any(pattern in name.lower() for pattern in obd_patterns):
                    result.append({"name": name, "address": address})
            
            return result

        # Run in a new event loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_discover())
        finally:
            loop.close()

    def __repr__(self) -> str:
        """String representation."""
        status = "open" if self._is_open else "closed"
        return f"BLEConnection(address={self.address}, status={status})"
