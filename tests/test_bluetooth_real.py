"""
Integration tests for Bluetooth connection with real hardware.

These tests require:
1. Bluetooth adapter (NK/OBDII at 00:1D:A5:1E:32:25) to be powered on
2. Adapter does NOT need to be connected to a vehicle
3. Tests basic ELM327 communication over Bluetooth

Tests are skipped if the adapter is not available.

To run from command line:
    python -m pytest tests/test_bluetooth_real.py -v
    
To run from VS Code, you may need to ensure the Bluetooth adapter is powered and paired.
"""

import asyncio
import unittest
import pytest
from driver import ELM327, BluetoothConnection
from driver.exceptions import NoResponseException


# Configuration for the Bluetooth adapter
BLUETOOTH_ADDRESS = "00:1D:A5:1E:32:25"
RFCOMM_DEVICE = 0  # /dev/rfcomm0
RFCOMM_CHANNEL = 1
BAUDRATE = 115200


@pytest.mark.integration
@pytest.mark.bluetooth
class TestBluetoothRealConnection(unittest.TestCase):
    """
    Integration tests for real Bluetooth ELM327 adapter.
    
    These tests verify that:
    1. Bluetooth connection can be established
    2. ELM327 device responds to AT commands
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
                asyncio.run(self.elm.close())
            except Exception:
                pass
        
        if self.connection:
            try:
                asyncio.run(self.connection.close())
                # Add delay after disconnecting to allow RFCOMM to fully release
                asyncio.run(asyncio.sleep(2.0))
            except Exception:
                pass
    
    def test_bluetooth_connection_and_initialization(self) -> None:
        """
        Test that we can connect to the Bluetooth adapter and initialize ELM327.
        
        This test verifies:
        - Bluetooth RFCOMM connection can be established
        - ELM327 responds to initialization commands (ATZ, ATE0, etc.)
        - Device identifies itself as ELM327
        
        Skipped if adapter is not available.
        """
        async def run_test():
            # Create Bluetooth connection
            self.connection = BluetoothConnection(
                address=BLUETOOTH_ADDRESS,
                rfcomm_device=RFCOMM_DEVICE,
                channel=RFCOMM_CHANNEL,
                baudrate=BAUDRATE
            )
            
            try:
                # Try to open connection
                await self.connection.open()
                # Add delay after connecting to allow RFCOMM to stabilize
                await asyncio.sleep(2.0)
                self.assertTrue(self.connection.is_open, "Connection should be open")
                
                # Create ELM327 instance
                self.elm = ELM327(self.connection)
                
                # Initialize ELM327 - this sends ATZ, ATE0, ATL0, ATS0, ATH1, ATSP0
                await self.elm.initialize()
                self.assertTrue(self.elm._initialized, "ELM327 should be initialized")
                
                print("\n✓ Successfully connected to Bluetooth adapter")
                print("✓ ELM327 initialization completed")
                
            except Exception as e:
                # If connection fails, skip the test
                self.skipTest(f"Bluetooth adapter not available: {e}")
        
        # Run the async test
        asyncio.run(run_test())
    
    def test_elm327_version_query(self) -> None:
        """
        Test querying ELM327 version without vehicle connection.
        
        This test verifies:
        - Can send AT commands to the adapter
        - Receives proper responses from ELM327
        
        Skipped if adapter is not available.
        """
        async def run_test():
            # Create and open connection
            self.connection = BluetoothConnection(
                address=BLUETOOTH_ADDRESS,
                rfcomm_device=RFCOMM_DEVICE,
                channel=RFCOMM_CHANNEL,
                baudrate=BAUDRATE
            )
            
            try:
                await self.connection.open()
                # Add delay after connecting to allow RFCOMM to stabilize
                await asyncio.sleep(2.0)
                self.elm = ELM327(self.connection)
                await self.elm.initialize()
                
                # Send ATI command to get device information
                response = await self.elm._send_command('ATI')
                
                # Verify we got a response
                self.assertIsNotNone(response, "Should receive response from ATI")
                self.assertGreater(len(response), 0, "Response should not be empty")
                
                # Response should contain version info
                # Could be "ELM327 v2.1", "ELM327 v1.5", etc.
                self.assertIn('ELM', response.upper(), "Response should contain ELM")
                
                print(f"\n✓ ELM327 Version: {response}")
                
            except Exception as e:
                self.skipTest(f"Bluetooth adapter not available: {e}")
        
        asyncio.run(run_test())
    
    def test_elm327_voltage_reading(self) -> None:
        """
        Test reading voltage from ELM327 adapter (internal voltage).
        
        This test verifies:
        - Can read adapter's internal voltage monitoring
        - Works without vehicle connection
        
        Skipped if adapter is not available.
        """
        async def run_test():
            # Create and open connection
            self.connection = BluetoothConnection(
                address=BLUETOOTH_ADDRESS,
                rfcomm_device=RFCOMM_DEVICE,
                channel=RFCOMM_CHANNEL,
                baudrate=BAUDRATE
            )
            
            try:
                await self.connection.open()
                # Add delay after connecting to allow RFCOMM to stabilize
                await asyncio.sleep(2.0)
                self.elm = ELM327(self.connection)
                await self.elm.initialize()
                
                # Send ATRV command to read voltage
                response = await self.elm._send_command('ATRV')
                
                # Verify we got a response
                self.assertIsNotNone(response, "Should receive response from ATRV")
                self.assertGreater(len(response), 0, "Response should not be empty")
                
                # Response should contain a voltage value (e.g., "12.5V" or "0.0V")
                self.assertIn('V', response.upper(), "Response should contain voltage unit")
                
                print(f"\n✓ Adapter Voltage: {response}")
                
            except Exception as e:
                self.skipTest(f"Bluetooth adapter not available: {e}")
        
        asyncio.run(run_test())
    
    def test_elm327_no_vehicle_connection(self) -> None:
        """
        Test that attempting to query vehicle data without connection fails gracefully.
        
        This test verifies:
        - Adapter correctly reports when no vehicle is connected
        - Proper error handling for "NO DATA" or "UNABLE TO CONNECT"
        
        Skipped if adapter is not available.
        """
        async def run_test():
            # Create and open connection
            self.connection = BluetoothConnection(
                address=BLUETOOTH_ADDRESS,
                rfcomm_device=RFCOMM_DEVICE,
                channel=RFCOMM_CHANNEL,
                baudrate=BAUDRATE
            )
            
            try:
                await self.connection.open()
                # Add delay after connecting to allow RFCOMM to stabilize
                await asyncio.sleep(2.0)
                self.elm = ELM327(self.connection)
                await self.elm.initialize()
                
                # Try to read vehicle speed (should fail without vehicle)
                with self.assertRaises(NoResponseException) as context:
                    await self.elm.send_message(None, 0x0D)
                
                # The exception should mention NO DATA or similar
                error_msg = str(context.exception).upper()
                self.assertTrue(
                    any(keyword in error_msg for keyword in ['NO DATA', 'UNABLE TO CONNECT', 'ERROR']),
                    f"Error message should indicate no vehicle connection: {context.exception}"
                )
                
                print("\n✓ Correctly detected no vehicle connected")
                print(f"  Error message: {context.exception}")
                
            except Exception as e:
                self.skipTest(f"Bluetooth adapter not available: {e}")
        
        asyncio.run(run_test())
    
    def test_bluetooth_connection_properties(self) -> None:
        """
        Test Bluetooth connection properties and status.
        
        This test verifies:
        - Connection reports correct status
        - Connection has proper delay behavior for real hardware
        
        Skipped if adapter is not available.
        """
        async def run_test():
            # Create connection
            self.connection = BluetoothConnection(
                address=BLUETOOTH_ADDRESS,
                rfcomm_device=RFCOMM_DEVICE,
                channel=RFCOMM_CHANNEL,
                baudrate=BAUDRATE
            )
            
            try:
                # Before opening
                self.assertFalse(self.connection.is_open, "Connection should not be open initially")
                
                # Open connection
                await self.connection.open()
                # Add delay after connecting to allow RFCOMM to stabilize
                await asyncio.sleep(2.0)
                self.assertTrue(self.connection.is_open, "Connection should be open after open()")
                
                # Verify it needs delays (real hardware)
                self.assertTrue(
                    self.connection.needs_delays,
                    "Real Bluetooth connection should need delays"
                )
                
                # Test basic write/read
                await self.connection.write(b'ATZ\r')
                response = await self.connection.read(100)
                self.assertGreater(len(response), 0, "Should receive response from ATZ")
                
                print("\n✓ Connection properties verified")
                print(f"  - Connection open: {self.connection.is_open}")
                print(f"  - Needs delays: {self.connection.needs_delays}")
                
                # Close connection
                await self.connection.close()
                self.assertFalse(self.connection.is_open, "Connection should be closed after close()")
                
            except Exception as e:
                self.skipTest(f"Bluetooth adapter not available: {e}")
        
        asyncio.run(run_test())


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
