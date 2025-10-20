#!/usr/bin/env python3
"""
Test script for Bluetooth connection to Vgate iCar Pro adapter.

This script discovers nearby Bluetooth devices and attempts to connect
to the Vgate adapter to verify the Bluetooth connection works.
"""

import asyncio
import sys

from bleak import BleakClient, BleakScanner


async def discover_devices() -> str | None:
    """Discover and list all available Bluetooth devices."""
    print("🔍 Scanning for Bluetooth devices...")
    print("-" * 80)

    try:
        scanner = BleakScanner()
        devices = await scanner.discover(timeout=5.0)

        if not devices:
            print("❌ No Bluetooth devices found.")
            return None

        print(f"✅ Found {len(devices)} device(s):\n")

        vgate_device = None
        for device in devices:
            print(f"  Name: {device.name}")
            print(f"  Address: {device.address}")
            print()

            # Look for Vgate/OBD device
            if device.name and any(
                pattern in device.name.lower()
                for pattern in ["vgate", "vlink", "obd", "icar"]
            ):
                vgate_device = device

        if vgate_device:
            print("=" * 80)
            print(f"✅ Found Vgate device: {vgate_device.name} ({vgate_device.address})")
            print("=" * 80)
            return vgate_device.address
        else:
            print("⚠️  No Vgate device found in the list.")
            print("   Make sure your Vgate adapter is powered on and in pairing mode.")
            return None

    except Exception as e:
        print(f"❌ Error during device discovery: {e}")
        return None


async def test_connection(address: str) -> bool:
    """Test connection to the Vgate adapter."""
    print("\n📡 Attempting to connect to Vgate adapter...")
    print("-" * 80)

    try:
        async with BleakClient(address) as client:
            print(f"✅ Connected to {address}")
            print(f"   Is connected: {client.is_connected}")

            # Get services
            services = client.services
            print(f"\n📋 Available services:")
            for service in services:
                print(f"   UUID: {service.uuid}")
                print(f"   Characteristics: {len(service.characteristics)}")
                for char in service.characteristics:
                    print(f"     - {char.uuid}: {char.properties}")

            print("\n✅ Connection test successful!")
            return True

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\n   Troubleshooting:")
        print("   1. Verify the adapter address is correct")
        print("   2. Ensure the Vgate adapter is powered on")
        print("   3. Make sure the adapter is not already connected to another device")
        print("   4. On Linux, you may need to run with sudo")
        return False


async def main() -> None:
    """Main test flow."""
    print("\n" + "=" * 80)
    print("🧪 Vgate iCar Pro Bluetooth Connection Test")
    print("=" * 80 + "\n")

    # Step 1: Discover devices
    vgate_address = await discover_devices()

    if not vgate_address:
        print("\n❌ Vgate device not found. Exiting.")
        sys.exit(1)

    # Step 2: Test connection
    success = await test_connection(vgate_address)

    print("\n" + "=" * 80)
    if success:
        print("✅ All tests passed! Bluetooth connection is working.")
        print("=" * 80 + "\n")
    else:
        print("❌ Connection test failed. Please check the device and try again.")
        print("=" * 80 + "\n")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
