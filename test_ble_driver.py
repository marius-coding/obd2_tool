#!/usr/bin/env python3
"""
Test script for the BLE connection driver with Vgate iCar Pro.

This script tests the BLEConnection class with a real BLE OBD2 dongle.
"""

import sys
import time
from driver.ble_connection import BLEConnection
from driver.elm327 import ELM327


def test_discovery():
    """Test BLE device discovery."""
    print("\n" + "=" * 80)
    print("Test 1: BLE Device Discovery")
    print("=" * 80)
    
    print("\n🔍 Scanning for all BLE devices...")
    devices = BLEConnection.discover_devices(timeout=10.0)
    
    if devices:
        print(f"✅ Found {len(devices)} BLE device(s):\n")
        for i, dev in enumerate(devices, 1):
            print(f"{i}. {dev['name']} - {dev['address']}")
    else:
        print("❌ No BLE devices found")
        return None
    
    print("\n🔍 Scanning for OBD2 devices...")
    obd_devices = BLEConnection.discover_obd_devices(timeout=10.0)
    
    if obd_devices:
        print(f"✅ Found {len(obd_devices)} OBD2 device(s):\n")
        for i, dev in enumerate(obd_devices, 1):
            print(f"{i}. {dev['name']} - {dev['address']}")
        return obd_devices[0]['address']
    else:
        print("⚠️  No OBD2 devices found")
        return None


def test_connection(address: str):
    """Test basic BLE connection."""
    print("\n" + "=" * 80)
    print("Test 2: BLE Connection")
    print("=" * 80)
    
    print(f"\n📡 Connecting to {address}...")
    
    try:
        conn = BLEConnection(address=address, timeout=10.0)
        conn.open()
        print("✅ Connection opened successfully")
        
        print(f"   Connection status: {conn}")
        
        # Small delay to let connection stabilize
        time.sleep(1.0)
        
        # Close connection
        conn.close()
        print("✅ Connection closed successfully")
        
        return True
    
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_raw_communication(address: str):
    """Test raw read/write to BLE device."""
    print("\n" + "=" * 80)
    print("Test 3: Raw BLE Communication")
    print("=" * 80)
    
    print(f"\n📡 Connecting to {address}...")
    
    try:
        conn = BLEConnection(address=address, timeout=10.0)
        conn.open()
        print("✅ Connected")
        
        # Flush any pending data
        conn.flush_input()
        
        # Send ATZ (reset)
        print("\n📤 Sending: ATZ")
        conn.write(b"ATZ\r")
        
        # Read response
        print("📥 Waiting for response...")
        response = conn.read_until(b">", timeout=5.0)
        print(f"✅ Received: {response.decode('ascii', errors='ignore').strip()}")
        
        # Send ATI (version)
        time.sleep(0.5)
        print("\n📤 Sending: ATI")
        conn.write(b"ATI\r")
        
        # Read response
        print("📥 Waiting for response...")
        response = conn.read_until(b">", timeout=5.0)
        print(f"✅ Received: {response.decode('ascii', errors='ignore').strip()}")
        
        # Close connection
        conn.close()
        print("\n✅ Raw communication test passed")
        
        return True
    
    except Exception as e:
        print(f"❌ Raw communication test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_elm327_protocol(address: str):
    """Test ELM327 protocol over BLE."""
    print("\n" + "=" * 80)
    print("Test 4: ELM327 Protocol via BLE")
    print("=" * 80)
    
    print(f"\n📡 Connecting to {address}...")
    
    try:
        # Create BLE connection
        conn = BLEConnection(address=address, timeout=10.0)
        conn.open()
        print("✅ Connected")
        
        # Create ELM327 protocol handler
        elm = ELM327(connection=conn)
        
        # Initialize ELM327
        print("🔧 Initializing ELM327...")
        elm.initialize()
        print("✅ ELM327 initialized")
        
        # Get version
        print("\n📤 Getting ELM327 version...")
        version = elm._send_command("ATI")
        print(f"✅ ELM327 Version: {version}")
        
        # Try to get voltage (works even without car connection)
        print("\n📤 Getting voltage...")
        try:
            response = elm._send_command("ATRV")
            print(f"✅ Voltage response: {response}")
        except Exception as e:
            print(f"⚠️  Voltage query failed (expected if not connected to car): {e}")
        
        # Close connection
        elm.close()
        print("\n✅ ELM327 protocol test passed")
        
        return True
    
    except Exception as e:
        print(f"❌ ELM327 protocol test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test execution."""
    print("\n" + "=" * 80)
    print("🧪 BLE Connection Driver Test Suite")
    print("=" * 80)
    print("\nThis test suite will:")
    print("  1. Discover BLE devices")
    print("  2. Test BLE connection")
    print("  3. Test raw BLE communication")
    print("  4. Test ELM327 protocol via BLE")
    print("\n" + "=" * 80)
    
    # Test 1: Discovery
    device_address = test_discovery()
    
    if not device_address:
        print("\n❌ No OBD2 devices found. Please ensure your device is:")
        print("   - Connected to 12V power")
        print("   - In pairing/advertising mode")
        print("   - Within range")
        sys.exit(1)
    
    # Test 2: Connection
    if not test_connection(device_address):
        print("\n❌ Connection test failed. Aborting further tests.")
        sys.exit(1)
    
    # Test 3: Raw communication
    if not test_raw_communication(device_address):
        print("\n⚠️  Raw communication test failed. Continuing anyway...")
    
    # Test 4: ELM327 protocol
    if not test_elm327_protocol(device_address):
        print("\n⚠️  ELM327 protocol test failed.")
    
    # Summary
    print("\n" + "=" * 80)
    print("✅ BLE Connection Driver Test Suite Complete!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
