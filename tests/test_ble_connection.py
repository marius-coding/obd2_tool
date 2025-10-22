"""
Unit tests for BLE connection layer (mocked, no hardware required).

These tests verify the BLEConnection class behavior using mocks,
so they don't require actual BLE hardware to run.

To run from command line:
    python -m pytest tests/test_ble_connection.py -v
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
import pytest
import threading
import time

from driver.ble_connection import BLEConnection
from driver.connection import ConnectionError, ConnectionException, ConnectionTimeoutError


class TestBLEConnectionUnit(unittest.TestCase):
    """Unit tests for BLEConnection class (mocked, no hardware)."""
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.mock_client = None
        self.connection = None
    
    def tearDown(self) -> None:
        """Clean up after tests."""
        if self.connection and self.connection.is_open:
            try:
                self.connection.close()
            except:
                pass
    
    def test_init_without_bleak(self) -> None:
        """Test initialization fails gracefully when bleak is not available."""
        with patch('driver.ble_connection.BLEAK_AVAILABLE', False):
            with self.assertRaises(ConnectionError) as context:
                BLEConnection(address="00:11:22:33:44:55")
            
            self.assertIn("bleak", str(context.exception).lower())
            self.assertIn("install", str(context.exception).lower())
    
    def test_init_with_parameters(self) -> None:
        """Test initialization with various parameters."""
        # Basic initialization
        conn = BLEConnection(address="AA:BB:CC:DD:EE:FF")
        self.assertEqual(conn.address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(conn.timeout, 10.0)  # Default
        self.assertFalse(conn.is_open)
        
        # With custom parameters
        conn = BLEConnection(
            address="11:22:33:44:55:66",
            timeout=15.0,
            service_uuid="custom-service-uuid",
            notify_uuid="custom-notify-uuid",
            write_uuid="custom-write-uuid"
        )
        self.assertEqual(conn.address, "11:22:33:44:55:66")
        self.assertEqual(conn.timeout, 15.0)
        self.assertEqual(conn._service_uuid, "custom-service-uuid")
        self.assertEqual(conn._notify_uuid, "custom-notify-uuid")
        self.assertEqual(conn._write_uuid, "custom-write-uuid")
    
    def test_connection_state(self) -> None:
        """Test connection state tracking."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        # Initially closed
        self.assertFalse(conn.is_open)
        
        # Mock open/close to test state
        with patch.object(conn, '_run_coroutine'):
            conn._is_open = True
            self.assertTrue(conn.is_open)
            
            conn._is_open = False
            self.assertFalse(conn.is_open)
    
    def test_needs_delays(self) -> None:
        """Test that BLE connection requires delays (real hardware)."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        self.assertTrue(conn.needs_delays, "BLE should need delays for real hardware")
    
    def test_repr(self) -> None:
        """Test string representation."""
        conn = BLEConnection(address="AA:BB:CC:DD:EE:FF")
        
        # When closed
        repr_str = repr(conn)
        self.assertIn("AA:BB:CC:DD:EE:FF", repr_str)
        self.assertIn("closed", repr_str)
        
        # When open
        conn._is_open = True
        repr_str = repr(conn)
        self.assertIn("AA:BB:CC:DD:EE:FF", repr_str)
        self.assertIn("open", repr_str)
    
    @patch('driver.ble_connection.BleakClient')
    def test_open_success(self, mock_bleak_client_class) -> None:
        """Test successful BLE connection opening."""
        # Create mock client
        mock_client = AsyncMock()
        mock_client.is_connected = True
        mock_client.services = []
        mock_bleak_client_class.return_value = mock_client
        
        conn = BLEConnection(
            address="00:11:22:33:44:55",
            notify_uuid="notify-uuid",
            write_uuid="write-uuid"
        )
        
        # Mock the coroutine runner
        with patch.object(conn, '_run_coroutine') as mock_run:
            mock_run.return_value = None
            conn._is_open = True  # Simulate successful open
            
            conn.open()
            
            # Should be open
            self.assertTrue(conn.is_open)
    
    def test_open_when_already_open(self) -> None:
        """Test opening an already open connection is a no-op."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        conn._is_open = True
        
        # Opening again should not raise error
        with patch.object(conn, '_run_coroutine') as mock_run:
            conn.open()
            # Should not call _run_coroutine if already open
            mock_run.assert_not_called()
    
    def test_close_when_already_closed(self) -> None:
        """Test closing an already closed connection is a no-op."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        # Closing when already closed should not raise error
        with patch.object(conn, '_run_coroutine') as mock_run:
            conn.close()
            # Should not call _run_coroutine if already closed
            mock_run.assert_not_called()
    
    def test_write_when_closed(self) -> None:
        """Test writing when connection is closed raises exception."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        with self.assertRaises(ConnectionException) as context:
            conn.write(b"test data")
        
        self.assertIn("not open", str(context.exception).lower())
    
    def test_read_when_closed(self) -> None:
        """Test reading when connection is closed raises exception."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        with self.assertRaises(ConnectionException) as context:
            conn.read(10)
        
        self.assertIn("not open", str(context.exception).lower())
    
    def test_read_until_when_closed(self) -> None:
        """Test read_until when connection is closed raises exception."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        with self.assertRaises(ConnectionException) as context:
            conn.read_until(b">")
        
        self.assertIn("not open", str(context.exception).lower())
    
    def test_notification_handler(self) -> None:
        """Test that notification handler adds data to buffer."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        # Simulate notification
        test_data = bytearray(b"test response")
        conn._notification_handler(None, test_data)
        
        # Data should be in buffer
        with conn._buffer_lock:
            self.assertEqual(conn._read_buffer, test_data)
    
    def test_read_from_buffer(self) -> None:
        """Test reading data from buffer."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        conn._is_open = True
        
        # Add data to buffer
        test_data = b"Hello World"
        with conn._buffer_lock:
            conn._read_buffer.extend(test_data)
        
        # Read 5 bytes
        result = conn.read(5)
        self.assertEqual(result, b"Hello")
        
        # Remaining data should still be in buffer
        with conn._buffer_lock:
            self.assertEqual(bytes(conn._read_buffer), b" World")
    
    def test_read_timeout(self) -> None:
        """Test that read times out when no data available."""
        conn = BLEConnection(address="00:11:22:33:44:55", timeout=0.1)
        conn._is_open = True
        
        # No data in buffer, should timeout
        with self.assertRaises(ConnectionTimeoutError) as context:
            conn.read(10)
        
        self.assertIn("timeout", str(context.exception).lower())
    
    def test_read_until_with_terminator_in_buffer(self) -> None:
        """Test read_until when terminator is already in buffer."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        conn._is_open = True
        
        # Add data with terminator
        test_data = b"ELM327 v2.3\r\r>"
        with conn._buffer_lock:
            conn._read_buffer.extend(test_data)
        
        # Read until >
        result = conn.read_until(b">")
        self.assertEqual(result, test_data)
        
        # Buffer should be empty
        with conn._buffer_lock:
            self.assertEqual(len(conn._read_buffer), 0)
    
    def test_read_until_with_partial_data(self) -> None:
        """Test read_until when data arrives in chunks."""
        conn = BLEConnection(address="00:11:22:33:44:55", timeout=1.0)
        conn._is_open = True
        
        # Add partial data
        with conn._buffer_lock:
            conn._read_buffer.extend(b"ELM327")
        
        # Add remaining data after a delay in another thread
        def add_more_data():
            time.sleep(0.1)
            with conn._buffer_lock:
                conn._read_buffer.extend(b" v2.3\r\r>")
        
        thread = threading.Thread(target=add_more_data)
        thread.start()
        
        # Read until > (should wait for complete data)
        result = conn.read_until(b">")
        self.assertEqual(result, b"ELM327 v2.3\r\r>")
        
        thread.join()
    
    def test_read_until_timeout(self) -> None:
        """Test that read_until times out when terminator never arrives."""
        conn = BLEConnection(address="00:11:22:33:44:55", timeout=0.1)
        conn._is_open = True
        
        # Add data without terminator
        with conn._buffer_lock:
            conn._read_buffer.extend(b"incomplete data")
        
        # Should timeout
        with self.assertRaises(ConnectionTimeoutError) as context:
            conn.read_until(b">")
        
        self.assertIn("timeout", str(context.exception).lower())
    
    def test_flush_input(self) -> None:
        """Test flushing input buffer."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        # Add data to buffer
        with conn._buffer_lock:
            conn._read_buffer.extend(b"some data to flush")
        
        # Flush
        conn.flush_input()
        
        # Buffer should be empty
        with conn._buffer_lock:
            self.assertEqual(len(conn._read_buffer), 0)
    
    def test_flush_output(self) -> None:
        """Test that flush_output is a no-op (BLE doesn't have output buffer)."""
        conn = BLEConnection(address="00:11:22:33:44:55")
        
        # Should not raise any errors
        conn.flush_output()
    
    @patch('driver.ble_connection.BleakScanner')
    def test_discover_devices(self, mock_scanner) -> None:
        """Test device discovery."""
        # Create mock devices
        mock_device1 = Mock()
        mock_device1.name = "Device 1"
        mock_device1.address = "11:22:33:44:55:66"
        
        mock_device2 = Mock()
        mock_device2.name = "Device 2"
        mock_device2.address = "AA:BB:CC:DD:EE:FF"
        
        # Mock discover method
        async def mock_discover(timeout):
            return [mock_device1, mock_device2]
        
        mock_scanner.discover = mock_discover
        
        # Discover devices
        devices = BLEConnection.discover_devices(timeout=5.0)
        
        # Should return list of devices
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]['name'], "Device 1")
        self.assertEqual(devices[0]['address'], "11:22:33:44:55:66")
        self.assertEqual(devices[1]['name'], "Device 2")
        self.assertEqual(devices[1]['address'], "AA:BB:CC:DD:EE:FF")
    
    @patch('driver.ble_connection.BleakScanner')
    def test_discover_devices_with_filter(self, mock_scanner) -> None:
        """Test device discovery with name filter."""
        # Create mock devices
        mock_device1 = Mock()
        mock_device1.name = "Vgate OBD"
        mock_device1.address = "11:22:33:44:55:66"
        
        mock_device2 = Mock()
        mock_device2.name = "Other Device"
        mock_device2.address = "AA:BB:CC:DD:EE:FF"
        
        # Mock discover method
        async def mock_discover(timeout):
            return [mock_device1, mock_device2]
        
        mock_scanner.discover = mock_discover
        
        # Discover with filter
        devices = BLEConnection.discover_devices(timeout=5.0, name_filter="Vgate")
        
        # Should only return matching device
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]['name'], "Vgate OBD")
    
    @patch('driver.ble_connection.BleakScanner')
    def test_discover_obd_devices(self, mock_scanner) -> None:
        """Test OBD2 device discovery."""
        # Create mock devices
        mock_obd1 = Mock()
        mock_obd1.name = "IOS-Vlink"
        mock_obd1.address = "11:22:33:44:55:66"
        
        mock_obd2 = Mock()
        mock_obd2.name = "Vgate iCar Pro"
        mock_obd2.address = "22:33:44:55:66:77"
        
        mock_other = Mock()
        mock_other.name = "Random Device"
        mock_other.address = "AA:BB:CC:DD:EE:FF"
        
        # Mock discover method
        async def mock_discover(timeout):
            return [mock_obd1, mock_obd2, mock_other]
        
        mock_scanner.discover = mock_discover
        
        # Discover OBD devices
        devices = BLEConnection.discover_obd_devices(timeout=5.0)
        
        # Should only return OBD devices
        self.assertEqual(len(devices), 2)
        names = [d['name'] for d in devices]
        self.assertIn("IOS-Vlink", names)
        self.assertIn("Vgate iCar Pro", names)
        self.assertNotIn("Random Device", names)


if __name__ == '__main__':
    unittest.main(verbosity=2)
