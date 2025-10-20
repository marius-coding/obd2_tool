#!/usr/bin/env python3
"""
Direct Bluetooth connection test to known paired OBD adapters.
"""

import asyncio
import sys
import pytest

from bleak import BleakClient

# Skip interactive Bluetooth direct tests during automated pytest runs
pytest.skip("Skipping interactive Bluetooth direct script in automated test runs", allow_module_level=True)


# Known OBD adapter addresses from bluetoothctl
OBD_ADAPTERS = {
    "Android-Vlink": "13:E0:2F:8D:5C:6B",
    "OBDII": "00:1D:A5:1E:32:25",
}


async def test_adapter_connection(name: str, address: str) -> bool:
    """Test connection to an OBD adapter."""
    print(f"\n📡 Testing {name} ({address})...")
    print("-" * 80)

    try:
        async with BleakClient(address) as client:
            if not client.is_connected:
                print(f"❌ Failed to connect to {name}")
                return False

            print(f"✅ Successfully connected to {name}")
            print(f"   Address: {address}")
            print(f"   Connected: {client.is_connected}")

            # Try to get services
            try:
                services = client.services
                if services:
                    print(f"\n   📋 Services available:")
                    service_count = 0
                    for service in services:
                        service_count += 1
                        char_count = len(service.characteristics)
                        print(f"      - {service.uuid} ({char_count} characteristics)")

                    print(f"\n   ✅ Found {service_count} service(s)")
                else:
                    print("   ⚠️  No services discovered")

            except Exception as e:
                print(f"   ⚠️  Could not read services: {e}")

            return True

    except asyncio.TimeoutError:
        print(f"❌ Connection timeout to {name}")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


async def main() -> None:
    """Test all known OBD adapters."""
    print("\n" + "=" * 80)
    print("🧪 OBD Adapter Bluetooth Connection Test")
    print("=" * 80)

    results = {}
    for name, address in OBD_ADAPTERS.items():
        success = await test_adapter_connection(name, address)
        results[name] = success

    # Summary
    print("\n" + "=" * 80)
    print("📊 Connection Summary:")
    print("=" * 80)

    successful = []
    failed = []

    for name, success in results.items():
        if success:
            print(f"✅ {name}: Connected successfully")
            successful.append(name)
        else:
            print(f"❌ {name}: Connection failed")
            failed.append(name)

    print("\n" + "=" * 80)
    if successful:
        print(f"✅ {len(successful)} adapter(s) connected successfully!")
        print(f"\nNext step: We can now implement the Bluetooth driver.")
        print("=" * 80 + "\n")
    else:
        print("❌ Could not connect to any adapters.")
        print("\nTroubleshooting:")
        print("1. Make sure the adapters are powered on")
        print("2. Check they are not connected to another device")
        print("3. Try: sudo systemctl restart bluetooth")
        print("4. Or run with: sudo python test_bluetooth_connection.py")
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
