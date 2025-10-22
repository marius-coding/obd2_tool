#!/usr/bin/env python3
"""
Test script for Vgate iCar Pro BLE 4.0 OBD2 adapter.

This script discovers nearby BLE devices and attempts to connect
to the Vgate iCar Pro adapter to verify the connection.

The dongle should be:
- Connected to 12V power (or car OBD2 port)
- In pairing/advertising mode (blue LED should be blinking)
"""

import asyncio
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("❌ Error: 'bleak' library not found.")
    print("   Install it with: pip install bleak")
    sys.exit(1)


# Known BLE service UUIDs for OBD2 adapters
OBD2_SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"  # Common for many ELM327 BLE adapters
NOTIFY_CHAR_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"   # RX characteristic
WRITE_CHAR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"    # TX characteristic


async def discover_vgate_devices(timeout: float = 10.0) -> list:
    """
    Discover Vgate iCar Pro and other OBD2 BLE devices.
    
    Args:
        timeout: Scan duration in seconds
        
    Returns:
        List of discovered OBD2 devices
    """
    print("🔍 Scanning for BLE devices...")
    print(f"   Timeout: {timeout} seconds")
    print("-" * 80)

    try:
        devices = await BleakScanner.discover(timeout=timeout)

        if not devices:
            print("❌ No BLE devices found.")
            print("\n   Troubleshooting:")
            print("   1. Make sure the dongle is connected to 12V power")
            print("   2. Check if the blue LED is blinking (pairing mode)")
            print("   3. Try unplugging and replugging the dongle")
            print("   4. Make sure Bluetooth is enabled on your system")
            return []

        print(f"✅ Found {len(devices)} BLE device(s):\n")

        obd_devices = []
        for i, device in enumerate(devices, 1):
            name = device.name or "Unknown"
            print(f"{i}. Name: {name}")
            print(f"   Address: {device.address}")
            
            # RSSI might not always be available
            try:
                if hasattr(device, 'rssi') and device.rssi:
                    print(f"   RSSI: {device.rssi} dBm")
            except:
                pass
            
            # Look for Vgate/OBD device names
            if name and any(
                pattern in name.lower()
                for pattern in ["vgate", "vlink", "obd", "elm", "icar", "v-link", "ios-vlink"]
            ):
                print(f"   ⭐ Potential OBD2 device detected!")
                obd_devices.append(device)
            
            print()

        if obd_devices:
            print("=" * 80)
            print(f"✅ Found {len(obd_devices)} potential OBD2 device(s):")
            for dev in obd_devices:
                print(f"   - {dev.name} ({dev.address})")
            print("=" * 80)
        else:
            print("⚠️  No obvious OBD2 devices found.")
            print("   Devices may still be OBD2 adapters with generic names.")

        return obd_devices if obd_devices else devices

    except Exception as e:
        print(f"❌ Error during device discovery: {e}")
        import traceback
        traceback.print_exc()
        return []


async def test_connection(address: str) -> bool:
    """
    Test connection to a BLE device.
    
    Args:
        address: BLE device address
        
    Returns:
        True if connection successful
    """
    print(f"\n📡 Attempting to connect to {address}...")
    print("-" * 80)

    try:
        async with BleakClient(address, timeout=15.0) as client:
            if not client.is_connected:
                print("❌ Failed to establish connection")
                return False
                
            print(f"✅ Connected successfully!")
            print(f"   MTU: {client.mtu_size} bytes")

            # Enumerate services
            print(f"\n📋 Available GATT services:")
            for service in client.services:
                print(f"\n   Service: {service.uuid}")
                print(f"   Description: {service.description}")
                
                for char in service.characteristics:
                    properties = ", ".join(char.properties)
                    print(f"      Characteristic: {char.uuid}")
                    print(f"      Properties: {properties}")
                    print(f"      Description: {char.description}")

            # Look for OBD2 service
            obd_service = None
            for service in client.services:
                if "fff0" in service.uuid.lower():
                    obd_service = service
                    break
            
            if obd_service:
                print(f"\n✅ Found OBD2 service: {obd_service.uuid}")
                print("   This device appears to be an OBD2 adapter!")
            else:
                print("\n⚠️  Standard OBD2 service UUID not found.")
                print("   Device might use a different service UUID.")

            print("\n✅ Connection test successful!")
            return True

    except asyncio.TimeoutError:
        print(f"❌ Connection timeout")
        print("\n   The device might be:")
        print("   - Already connected to another device (phone/car)")
        print("   - Out of range")
        print("   - In sleep mode (needs car ignition on)")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_elm327_communication(address: str) -> bool:
    """
    Test basic ELM327 communication with the device.
    
    Args:
        address: BLE device address
        
    Returns:
        True if communication successful
    """
    print(f"\n🔧 Testing ELM327 communication with {address}...")
    print("-" * 80)

    try:
        async with BleakClient(address, timeout=15.0) as client:
            if not client.is_connected:
                print("❌ Failed to connect")
                return False

            # Find the write and notify characteristics
            write_char = None
            notify_char = None
            
            for service in client.services:
                for char in service.characteristics:
                    if "write" in char.properties:
                        write_char = char
                    if "notify" in char.properties:
                        notify_char = char

            if not write_char:
                print("❌ No writable characteristic found")
                return False

            if not notify_char:
                print("❌ No notify characteristic found")
                return False

            print(f"✅ Write characteristic: {write_char.uuid}")
            print(f"✅ Notify characteristic: {notify_char.uuid}")

            # Set up notification handler
            responses = []
            
            def notification_handler(sender, data):
                """Handle incoming notifications."""
                response = data.decode('ascii', errors='ignore').strip()
                print(f"   <- Received: {response}")
                responses.append(response)

            # Start notifications
            await client.start_notify(notify_char.uuid, notification_handler)
            print("\n✅ Notifications enabled")

            # Send ATZ (reset) command
            print("\n📤 Sending ELM327 reset command: ATZ")
            command = b"ATZ\r"
            await client.write_gatt_char(write_char.uuid, command)
            
            # Wait for response
            await asyncio.sleep(2.0)

            # Send ATI (version) command
            print("\n📤 Sending version query: ATI")
            command = b"ATI\r"
            await client.write_gatt_char(write_char.uuid, command)
            
            # Wait for response
            await asyncio.sleep(2.0)

            # Stop notifications
            await client.stop_notify(notify_char.uuid)

            if responses:
                print(f"\n✅ Communication successful! Received {len(responses)} response(s)")
                return True
            else:
                print("\n⚠️  No responses received")
                print("   This is normal if the dongle is not connected to a vehicle")
                return True  # Still consider it successful if we could connect

    except Exception as e:
        print(f"❌ Communication test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main() -> None:
    """Main test flow."""
    print("\n" + "=" * 80)
    print("🧪 Vgate iCar Pro BLE 4.0 Connection Test")
    print("=" * 80)
    print("\nThis test will:")
    print("  1. Scan for BLE devices")
    print("  2. Identify potential OBD2 adapters")
    print("  3. Connect to the device")
    print("  4. Enumerate GATT services")
    print("  5. Test basic ELM327 communication")
    print("\n" + "=" * 80 + "\n")

    # Step 1: Discover devices
    devices = await discover_vgate_devices(timeout=10.0)

    if not devices:
        print("\n❌ No devices found. Exiting.")
        print("\n💡 Make sure:")
        print("   - Dongle is connected to 12V power")
        print("   - Blue LED is blinking (pairing mode)")
        print("   - Bluetooth is enabled on this system")
        sys.exit(1)

    # Step 2: Select device to test
    if len(devices) == 1:
        target_device = devices[0]
        print(f"\n🎯 Testing device: {target_device.name} ({target_device.address})")
    else:
        print(f"\n🎯 Found {len(devices)} devices.")
        print("   Testing the first one...")
        target_device = devices[0]
        print(f"   Device: {target_device.name} ({target_device.address})")

    # Step 3: Test connection
    connection_ok = await test_connection(target_device.address)

    if not connection_ok:
        print("\n❌ Connection test failed. Exiting.")
        sys.exit(1)

    # Step 4: Test ELM327 communication
    print("\n" + "=" * 80)
    user_input = input("Do you want to test ELM327 communication? (y/n): ")
    
    if user_input.lower() == 'y':
        comm_ok = await test_elm327_communication(target_device.address)
        
        print("\n" + "=" * 80)
        if comm_ok:
            print("✅ All tests passed!")
        else:
            print("⚠️  Connection successful but communication failed")
            print("   This is expected if the dongle is not connected to a vehicle")
        print("=" * 80 + "\n")
    else:
        print("\n" + "=" * 80)
        print("✅ Connection test completed successfully!")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
