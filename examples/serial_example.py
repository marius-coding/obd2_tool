"""
Example: Using ELM327 with Serial connection.

This example demonstrates how to connect to an ELM327 adapter via USB/Serial
and perform basic OBD-II queries.
"""

import asyncio
from driver import ELM327, SerialConnection


async def main():
    """Main example function."""
    # Serial port (replace with your port)
    # Linux: /dev/ttyUSB0, /dev/ttyACM0, etc.
    # Windows: COM3, COM4, etc.
    # macOS: /dev/cu.usbserial-*
    serial_port = "/dev/ttyUSB0"
    
    # Create Serial connection
    connection = SerialConnection(
        port=serial_port,
        baudrate=38400,     # Common: 38400, 115200
        timeout=1.0
    )
    
    try:
        # Open the connection using async context manager
        async with connection:
            print(f"Connected to serial port {serial_port}")
            
            # Create ELM327 driver with the connection
            elm = ELM327(connection)
            
            # Initialize ELM327
            await elm.initialize()
            print("ELM327 initialized successfully")
            
            # Example 1: Read vehicle speed (PID 0x0D)
            print("\n=== Reading Vehicle Speed (PID 0x0D) ===")
            try:
                response = await elm.send_message(None, 0x0D)
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
                response = await elm.send_message(None, 0x0C)
                if response.data and len(response.data) >= 2:
                    rpm = ((response.data[0] * 256) + response.data[1]) / 4
                    print(f"Engine RPM: {rpm}")
                else:
                    print("No RPM data received")
            except Exception as e:
                print(f"Error reading RPM: {e}")
            
            # Example 3: Read coolant temperature (PID 0x05)
            print("\n=== Reading Coolant Temperature (PID 0x05) ===")
            try:
                response = await elm.send_message(None, 0x05)
                if response.data and len(response.data) > 0:
                    temp = response.data[0] - 40  # Temperature in °C
                    print(f"Coolant temperature: {temp}°C")
                else:
                    print("No temperature data received")
            except Exception as e:
                print(f"Error reading temperature: {e}")
            
            # Close the ELM327 driver
            await elm.close()
            print("\n=== Connection closed ===")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
