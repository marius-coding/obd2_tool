#!/usr/bin/env python3
"""
Test script for Bluetooth connection to OBD2 adapters using Serial Port Profile (RFCOMM).

This script tests connection to classic Bluetooth OBD2 adapters using the
Serial Port Profile (RFCOMM) which is standard for OBD2 devices.
"""

import subprocess
import sys
import time


# Known OBD2 adapter addresses
OBD_ADAPTERS = {
    "OBDII": "00:1D:A5:1E:32:25",
    "Android-Vlink": "13:E0:2F:8D:5C:6B",
}


def get_rfcomm_port(address: str) -> str | None:
    """Get available RFCOMM port for an address."""
    # Try to get an available RFCOMM channel
    result = subprocess.run(
        ["rfcomm", "search", address],
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode == 0 and result.stdout:
        # Parse output to get channel number
        for line in result.stdout.split("\n"):
            if "Channel:" in line:
                parts = line.split()
                return parts[-1]
    return None


def test_adapter_connection(name: str, address: str) -> bool:
    """Test connection to an OBD2 adapter."""
    print(f"\n📡 Testing {name} ({address})...")
    print("-" * 80)

    try:
        # Try to connect using bluetoothctl
        result = subprocess.run(
            ["bluetoothctl", "connect", address],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            print(f"❌ Failed to connect: {result.stderr}")
            return False

        # Wait a moment for connection to establish
        time.sleep(1)

        # Check connection status
        info_result = subprocess.run(
            ["bluetoothctl", "info", address],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if "Connected: yes" in info_result.stdout:
            print(f"✅ Successfully connected to {name}")
            print(f"   Address: {address}")

            # Try to bind RFCOMM port
            try:
                bind_result = subprocess.run(
                    ["sudo", "rfcomm", "bind", "/dev/rfcomm0", address],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )

                if bind_result.returncode == 0 or "Device or resource busy" in bind_result.stderr:
                    print(f"   ✅ RFCOMM port available at /dev/rfcomm0")

                    # Try to open and communicate with the port
                    try:
                        with open("/dev/rfcomm0", "rb", buffering=0) as port:
                            print(f"   ✅ RFCOMM port is readable")
                            # Try to send an ELM327 init command
                            port_write = open("/dev/rfcomm0", "wb", buffering=0)
                            port_write.write(b"ATZ\r")  # Reset command
                            port_write.close()
                            print(f"   ✅ Sent test command to adapter")

                    except Exception as e:
                        print(f"   ⚠️  Could not read from port: {e}")

                else:
                    print(f"   ⚠️  Could not bind RFCOMM: {bind_result.stderr}")

            except Exception as e:
                print(f"   ⚠️  RFCOMM binding not available: {e}")

            return True

        else:
            print(f"❌ Device shows not connected")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ Connection timeout to {name}")
        return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def cleanup():
    """Clean up RFCOMM bindings."""
    try:
        subprocess.run(["sudo", "rfcomm", "release", "all"], capture_output=True, timeout=5)
    except:
        pass


async def main() -> None:
    """Test all known OBD adapters."""
    print("\n" + "=" * 80)
    print("🧪 OBD2 Adapter Bluetooth Connection Test")
    print("=" * 80)

    results = {}
    for name, address in OBD_ADAPTERS.items():
        success = test_adapter_connection(name, address)
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
        print("4. Or run with: sudo python test_bluetooth_direct.py")
        print("=" * 80 + "\n")
        sys.exit(1)

    # Cleanup
    cleanup()


if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user.")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        cleanup()
        sys.exit(1)
