"""
Example: Using ELM327 with Bluetooth connection.

This example demonstrates how to connect to an ELM327 adapter via Bluetooth
and perform basic OBD-II queries.
"""

from driver import ELM327, BluetoothConnection


def main():
    """Main example function."""
    # Bluetooth adapter address (replace with your adapter's address)
    bluetooth_address = "00:1D:A5:1E:32:25"
    
    # Create Bluetooth connection
    # The connection uses RFCOMM channel 1 by default
    connection = BluetoothConnection(
        address=bluetooth_address,
        rfcomm_device=0,  # Uses /dev/rfcomm0
        channel=1,        # RFCOMM channel
        baudrate=115200   # Typically 38400 or 115200
    )
    
    try:
        # Open the connection using context manager
        with connection:
            print(f"Connected to Bluetooth adapter at {bluetooth_address}")

            # Create ELM327 driver with the connection
            elm = ELM327(connection)

            # Initialize ELM327
            elm.initialize()
            print("ELM327 initialized successfully")
            
            # Example 1: Read vehicle speed (PID 0x0D)
            print("\n=== Reading Vehicle Speed (PID 0x0D) ===")
            try:
                response = elm.send_message(None, 0x0D)
                if response.data and len(response.data) > 0:
                    speed = response.data[0]
                    print(f"Vehicle speed: {speed} km/h")
                else:
                    print("No speed data received")
            except Exception as e:
                print(f"Error reading speed: {e}")
            
            # Example 2: Read engine RPM (PID 0x0C)
            print("\n=== Reading Engine RPM (PID 0x0C) ===")
            try:
                response = elm.send_message(None, 0x0C)
                if response.data and len(response.data) >= 2:
                    rpm = ((response.data[0] * 256) + response.data[1]) / 4
                    print(f"Engine RPM: {rpm}")
                else:
                    print("No RPM data received")
            except Exception as e:
                print(f"Error reading RPM: {e}")
            
            # Example 3: UDS request (if supported by your vehicle)
            # Read VIN using UDS service 0x22 with DID 0xF190
            print("\n=== Reading VIN via UDS ===")
            try:
                # Set CAN ID for your vehicle's ECU (example: 0x7E0 for engine ECU)
                can_id = 0x7E0
                service_did = 0x22F190  # Service 0x22, DID 0xF190
                
                response = elm.send_message(can_id, service_did)
                if response.data:
                    vin = bytes(response.data).decode('ascii', errors='ignore')
                    print(f"VIN: {vin}")
                else:
                    print("No VIN data received")
            except Exception as e:
                print(f"Error reading VIN: {e}")
            
            # Close the ELM327 driver
            elm.close()
            print("\n=== Connection closed ===")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
