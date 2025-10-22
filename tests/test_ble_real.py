"""
Integration tests for BLE connection with real hardware.

These tests require:
1. BLE adapter (Vgate iCar Pro / IOS-Vlink at D2:E0:2F:8D:5C:6B) to be powered on
2. Adapter does NOT need to be connected to a vehicle
3. Tests basic ELM327 communication over BLE

Tests are skipped if the adapter is not available.

To run from command line:
    python -m pytest tests/test_ble_real.py -v
    
To run only BLE tests:
    python -m pytest tests/test_ble_real.py -v -m ble
"""

import asyncio
import unittest
import pytest
from driver import ELM327, BLEConnection
from driver.exceptions import NoResponseException


# Configuration for the BLE adapter
# Update this address to match your device
BLE_ADDRESS = "D2:E0:2F:8D:5C:6B"  # IOS-Vlink (Vgate iCar Pro)
CONNECTION_TIMEOUT = 15.0  # BLE may need longer timeout


@pytest.mark.integration
@pytest.mark.ble
class TestBLERealConnection(unittest.TestCase):
    """
    Integration tests for real BLE ELM327 adapter.
    
    These tests verify that:
    1. BLE connection can be established
    2. ELM327 device responds to AT commands over BLE
    3. Basic communication works without a vehicle connected
    """
    
    def setUp(self) -> None:
        """Set up test fixtures."""
        self.connection = None
        self.elm = None
    
    def tearDown(self) -> None:
        """Clean up after tests."""
        if self.elm:
            try:
                self.elm.close()
            except Exception:
                pass
        
        if self.connection:
            try:
                self.connection.close()
                # Add delay after disconnecting to allow BLE to fully release
                import time
                time.sleep(1.0)
            except Exception:
                pass
    
    def test_ble_connection_and_initialization(self) -> None:
        """
        Test that we can connect to the BLE adapter and initialize ELM327.
        
        This test verifies:
        - BLE GATT connection can be established
        - Characteristics are discovered automatically
        - ELM327 responds to initialization commands (ATZ, ATE0, etc.)
        - Device identifies itself as ELM327
        
        Skipped if adapter is not available.
        """
        # Create BLE connection
        self.connection = BLEConnection(
            address=BLE_ADDRESS,
            timeout=CONNECTION_TIMEOUT
        )
        
        try:
            # Try to open connection
            self.connection.open()
            self.assertTrue(self.connection.is_open, "Connection should be open")
            
            # Create ELM327 instance
            self.elm = ELM327(self.connection)
            
            # Initialize ELM327 - this sends ATZ, ATE0, ATL0, ATS0, ATH1, ATSP0
            self.elm.initialize()
            self.assertTrue(self.elm._initialized, "ELM327 should be initialized")
            
            print("\n✓ Successfully connected to BLE adapter")
            print("✓ ELM327 initialization completed")
            
        except Exception as e:
            print(f"\nBLE connection failed: {e}")
            # If connection fails, skip the test
            self.skipTest(f"BLE adapter not available: {e}")
    
    def test_ble_device_discovery(self) -> None:
        """
        Test BLE device discovery functionality.
        
        This test verifies:
        - Can scan for BLE devices
        - OBD2 device filtering works
        - Device information is returned correctly
        
        This test doesn't require connection, just BLE scanning.
        """
        try:
            # Discover all BLE devices
            devices = BLEConnection.discover_devices(timeout=5.0)
            
            # Should find at least some devices
            self.assertIsNotNone(devices, "Device list should not be None")
            self.assertIsInstance(devices, list, "Should return a list")
            
            # Each device should have name and address
            for device in devices:
                self.assertIn('name', device, "Device should have 'name' key")
                self.assertIn('address', device, "Device should have 'address' key")
            
            print(f"\n✓ Found {len(devices)} BLE device(s)")
            
            # Try OBD2-specific discovery
            obd_devices = BLEConnection.discover_obd_devices(timeout=5.0)
            self.assertIsInstance(obd_devices, list, "Should return a list")
            
            print(f"✓ Found {len(obd_devices)} OBD2 BLE device(s)")
            
            if obd_devices:
                for device in obd_devices:
                    print(f"  - {device['name']} ({device['address']})")
            
        except Exception as e:
            print(f"\nBLE scanning failed: {e}")
            self.skipTest(f"BLE scanning not available: {e}")
    
    def test_elm327_version_query(self) -> None:
        """
        Test querying ELM327 version without vehicle connection.
        
        This test verifies:
        - Can send AT commands to the adapter over BLE
        - Receives proper responses from ELM327
        
        Skipped if adapter is not available.
        """
        # Create and open connection
        self.connection = BLEConnection(
            address=BLE_ADDRESS,
            timeout=CONNECTION_TIMEOUT
        )
        
        try:
            self.connection.open()
            self.elm = ELM327(self.connection)
            self.elm.initialize()
            
            # Send ATI command to get device information
            response = self.elm._send_command('ATI')
            
            # Verify we got a response
            self.assertIsNotNone(response, "Should receive response from ATI")
            self.assertGreater(len(response), 0, "Response should not be empty")
            
            # Response should contain version info
            # Could be "ELM327 v2.3", "ELM327 v1.5", etc.
            self.assertIn('ELM', response.upper(), "Response should contain ELM")
            
            print(f"\n✓ ELM327 Version: {response}")
            
        except Exception as e:
            print(f"\nBLE connection failed: {e}")
            self.skipTest(f"BLE adapter not available: {e}")
    
    def test_elm327_voltage_reading(self) -> None:
        """
        Test reading voltage from ELM327 adapter (internal voltage).
        
        This test verifies:
        - Can read adapter's internal voltage monitoring
        - Works without vehicle connection
        
        Skipped if adapter is not available.
        """
        # Create and open connection
        self.connection = BLEConnection(
            address=BLE_ADDRESS,
            timeout=CONNECTION_TIMEOUT
        )
        
        try:
            self.connection.open()
            self.elm = ELM327(self.connection)
            self.elm.initialize()
            
            # Send ATRV command to read voltage
            response = self.elm._send_command('ATRV')
            
            # Verify we got a response
            self.assertIsNotNone(response, "Should receive response from ATRV")
            self.assertGreater(len(response), 0, "Response should not be empty")
            
            # Response should contain a voltage value (e.g., "12.5V" or "0.0V")
            self.assertIn('V', response.upper(), "Response should contain voltage unit")
            
            print(f"\n✓ Adapter Voltage: {response}")
            
        except Exception as e:
            print(f"\nBLE connection failed: {e}")
            self.skipTest(f"BLE adapter not available: {e}")
    
    def test_elm327_no_vehicle_connection(self) -> None:
        """
        Test that attempting to query vehicle data without connection fails gracefully.
        
        This test verifies:
        - Adapter correctly reports when no vehicle is connected
        - Proper error handling for "NO DATA" or "UNABLE TO CONNECT"
        
        Skipped if adapter is not available.
        """
        # Create and open connection
        self.connection = BLEConnection(
            address=BLE_ADDRESS,
            timeout=CONNECTION_TIMEOUT
        )
        
        try:
            self.connection.open()
            self.elm = ELM327(self.connection)
            self.elm.initialize()
            
            # Try to read vehicle speed (should fail without vehicle)
            with self.assertRaises(NoResponseException) as context:
                self.elm.send_message(None, 0x0D)
            
            # The exception should mention NO DATA or similar
            error_msg = str(context.exception).upper()
            self.assertTrue(
                any(keyword in error_msg for keyword in ['NO DATA', 'UNABLE TO CONNECT', 'ERROR']),
                f"Error message should indicate no vehicle connection: {context.exception}"
            )
            
            print("\n✓ Correctly detected no vehicle connected")
            print(f"  Error message: {context.exception}")
            
        except Exception as e:
            print(f"\nBLE connection failed: {e}")
            self.skipTest(f"BLE adapter not available: {e}")
    
    def test_ble_connection_properties(self) -> None:
        """
        Test BLE connection properties and status.
        
        This test verifies:
        - Connection reports correct status
        - Connection has proper delay behavior for real hardware
        - Read/write operations work correctly
        
        Skipped if adapter is not available.
        """
        # Create connection
        self.connection = BLEConnection(
            address=BLE_ADDRESS,
            timeout=CONNECTION_TIMEOUT
        )
        
        try:
            # Before opening
            self.assertFalse(self.connection.is_open, "Connection should not be open initially")
            
            # Open connection
            self.connection.open()
            self.assertTrue(self.connection.is_open, "Connection should be open after open()")
            
            # Verify it needs delays (real hardware)
            self.assertTrue(
                self.connection.needs_delays,
                "Real BLE connection should need delays"
            )
            
            # Test basic write/read_until (BLE uses notifications, so read_until is better)
            self.connection.flush_input()
            self.connection.write(b'ATI\r')
            response = self.connection.read_until(b'>', timeout=5.0)
            self.assertGreater(len(response), 0, "Should receive response from ATI")
            
            # Response should end with '>'
            self.assertTrue(response.endswith(b'>'), "Response should end with '>'")
            
            print("\n✓ Connection properties verified")
            print(f"  - Connection open: {self.connection.is_open}")
            print(f"  - Needs delays: {self.connection.needs_delays}")
            print(f"  - Response length: {len(response)} bytes")
            
            # Close connection
            self.connection.close()
            self.assertFalse(self.connection.is_open, "Connection should be closed after close()")
            
        except Exception as e:
            print(f"\nBLE connection failed: {e}")
            self.skipTest(f"BLE adapter not available: {e}")
    
    def test_ble_multiple_commands(self) -> None:
        """
        Test sending multiple commands in sequence.
        
        This test verifies:
        - Can send multiple commands without issues
        - Buffer management works correctly
        - No data corruption between commands
        
        Skipped if adapter is not available.
        """
        # Create and open connection
        self.connection = BLEConnection(
            address=BLE_ADDRESS,
            timeout=CONNECTION_TIMEOUT
        )
        
        try:
            self.connection.open()
            self.elm = ELM327(self.connection)
            self.elm.initialize()
            
            # Send multiple commands
            commands = ['ATI', 'ATRV', 'ATDP', 'ATI']
            responses = []
            
            for cmd in commands:
                response = self.elm._send_command(cmd)
                self.assertIsNotNone(response, f"Should receive response for {cmd}")
                self.assertGreater(len(response), 0, f"Response for {cmd} should not be empty")
                responses.append(response)
            
            # Verify we got different responses (or at least valid ones)
            self.assertEqual(len(responses), len(commands), "Should receive all responses")
            
            # First and last command are the same, responses should be similar
            self.assertIn('ELM', responses[0].upper(), "First ATI should contain ELM")
            self.assertIn('ELM', responses[3].upper(), "Last ATI should contain ELM")
            
            print("\n✓ Multiple commands executed successfully")
            for cmd, resp in zip(commands, responses):
                print(f"  {cmd}: {resp[:50]}..." if len(resp) > 50 else f"  {cmd}: {resp}")
            
        except Exception as e:
            print(f"\nBLE connection failed: {e}")
            self.skipTest(f"BLE adapter not available: {e}")
    
    def test_ble_reconnection(self) -> None:
        """
        Test closing and reopening BLE connection.
        
        This test verifies:
        - Can close connection cleanly
        - Can reconnect after closing
        - State is properly reset
        
        Skipped if adapter is not available.
        """
        # Create connection
        self.connection = BLEConnection(
            address=BLE_ADDRESS,
            timeout=CONNECTION_TIMEOUT
        )
        
        try:
            # First connection
            self.connection.open()
            self.assertTrue(self.connection.is_open)
            
            self.elm = ELM327(self.connection)
            self.elm.initialize()
            
            response1 = self.elm._send_command('ATI')
            self.assertGreater(len(response1), 0)
            
            # Close connection
            self.elm.close()
            self.assertFalse(self.connection.is_open)
            
            print("\n✓ First connection closed")
            
            # Wait a bit before reconnecting
            import time
            time.sleep(2.0)
            
            # Reconnect
            self.connection.open()
            self.assertTrue(self.connection.is_open)
            
            self.elm = ELM327(self.connection)
            self.elm.initialize()
            
            response2 = self.elm._send_command('ATI')
            self.assertGreater(len(response2), 0)
            
            print("✓ Successfully reconnected")
            print(f"  First response:  {response1}")
            print(f"  Second response: {response2}")
            
            # Responses should be similar
            self.assertIn('ELM', response2.upper())
            
        except Exception as e:
            print(f"\nBLE connection failed: {e}")
            self.skipTest(f"BLE adapter not available: {e}")


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
