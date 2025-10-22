#!/usr/bin/env python3
"""
Example of using BLE connection with Vgate iCar Pro OBD2 adapter.

This example demonstrates how to:
1. Discover OBD2 BLE devices
2. Connect to a Vgate iCar Pro adapter
3. Initialize ELM327 protocol
4. Send commands and read responses

Requirements:
- Vgate iCar Pro or compatible BLE OBD2 adapter
- Adapter must be powered (connected to 12V or car OBD2 port)
- bleak library installed (pip install bleak)
"""

from driver import BLEConnection, ELM327


def discover_and_select_device():
    """Discover OBD2 BLE devices and let user select one."""
    print("🔍 Scanning for OBD2 BLE devices...")
    print("   This may take up to 10 seconds...")
    print()
    
    devices = BLEConnection.discover_obd_devices(timeout=10.0)
    
    if not devices:
        print("❌ No OBD2 devices found.")
        print("\n💡 Make sure your device is:")
        print("   - Connected to 12V power (or car OBD2 port)")
        print("   - In pairing/advertising mode (LED blinking)")
        print("   - Within Bluetooth range")
        return None
    
    print(f"✅ Found {len(devices)} OBD2 device(s):\n")
    for i, dev in enumerate(devices, 1):
        print(f"{i}. {dev['name']} - {dev['address']}")
    
    if len(devices) == 1:
        return devices[0]['address']
    
    # Let user select
    while True:
        try:
            choice = input(f"\nSelect device (1-{len(devices)}): ")
            index = int(choice) - 1
            if 0 <= index < len(devices):
                return devices[index]['address']
        except (ValueError, KeyboardInterrupt):
            return None


def main():
    """Main example function."""
    print("\n" + "=" * 80)
    print("🚗 Vgate iCar Pro BLE Connection Example")
    print("=" * 80 + "\n")
    
    # Step 1: Discover devices
    address = discover_and_select_device()
    
    if not address:
        print("\n❌ No device selected. Exiting.")
        return
    
    print(f"\n📡 Connecting to {address}...\n")
    
    try:
        # Step 2: Create BLE connection
        conn = BLEConnection(
            address=address,
            timeout=10.0,
        )
        
        # Open connection
        conn.open()
        print("✅ BLE connection established\n")
        
        # Step 3: Create ELM327 protocol handler
        elm = ELM327(connection=conn)
        
        # Initialize ELM327
        print("🔧 Initializing ELM327...")
        elm.initialize()
        print("✅ ELM327 initialized\n")
        
        # Step 4: Get adapter information
        print("📋 Adapter Information:")
        print("-" * 80)
        
        # Get version
        print("📤 ATI (Get version)...")
        version = elm._send_command("ATI")
        print(f"   Version: {version}\n")
        
        # Get voltage (if connected to car)
        print("📤 ATRV (Get voltage)...")
        try:
            voltage = elm._send_command("ATRV")
            print(f"   Voltage: {voltage}\n")
        except Exception as e:
            print(f"   ⚠️  Not available (dongle not connected to car): {e}\n")
        
        # Get protocol
        print("📤 ATDP (Describe protocol)...")
        try:
            protocol = elm._send_command("ATDP")
            print(f"   Protocol: {protocol}\n")
        except Exception as e:
            print(f"   ⚠️  Not available: {e}\n")
        
        print("-" * 80)
        
        # Step 5: If connected to a car, try to read VIN
        if input("\n🚗 Is the dongle connected to a car? (y/n): ").lower() == 'y':
            print("\n📤 Attempting to read VIN...")
            try:
                # Request VIN (Service 09, PID 02)
                response = elm._send_command("0902")
                print(f"   VIN Response: {response}")
                
                # Parse VIN (this is simplified - real parsing is more complex)
                if "49 02" in response:
                    print("   ✅ VIN data received (parsing not implemented in this example)")
                else:
                    print("   ⚠️  No VIN data received")
            except Exception as e:
                print(f"   ❌ VIN read failed: {e}")
        
        # Step 6: Close connection
        print("\n📡 Closing connection...")
        elm.close()
        print("✅ Connection closed")
        
        print("\n" + "=" * 80)
        print("✅ Example completed successfully!")
        print("=" * 80 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
