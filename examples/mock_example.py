"""
Example: Using ELM327 with Mock connection for testing.

This example demonstrates how to use the MockConnection for testing
without requiring actual hardware.
"""

import asyncio
from driver import ELM327, MockConnection


async def main():
    """Main example function."""
    # Create Mock connection
    connection = MockConnection()
    
    try:
        # Open the connection using async context manager
        async with connection:
            print("Connected to mock ELM327 adapter")
            
            # Create ELM327 driver with the connection
            elm = ELM327(connection)
            
            # Initialize ELM327
            await elm.initialize()
            print("ELM327 initialized successfully")
            
            # Example 1: UDS request to read battery data (predefined mock response)
            print("\n=== Reading Battery Data via UDS (Service 0x22, DID 0x0101) ===")
            try:
                # Set CAN ID for battery ECU
                can_id = 0x7E4
                
                # This mock has a predefined response for this request
                response = await elm.send_message(can_id, 0x220101)
                if response.data:
                    print(f"Received {len(response.data)} bytes of data")
                    print(f"Service ID: 0x{response.service_id:02X}")
                    if response.data_identifier:
                        print(f"Data ID: 0x{response.data_identifier:04X}")
                    
                    # Battery SOC is typically at a specific offset
                    # This is just an example - actual parsing depends on vehicle
                    if len(response.data) >= 32:
                        soc_raw = (response.data[30] << 8) | response.data[31]
                        soc = soc_raw / 2.0  # Example calculation
                        print(f"Battery State of Charge: {soc}%")
                else:
                    print("No data received")
            except Exception as e:
                print(f"Error: {e}")
            
            # Example 2: Another UDS request (battery cell voltages)
            print("\n=== Reading Battery Cell Data (Service 0x22, DID 0x0105) ===")
            try:
                response = await elm.send_message(0x7E4, 0x220105)
                if response.data:
                    print(f"Received {len(response.data)} bytes of cell data")
                    print(f"Service ID: 0x{response.service_id:02X}")
                else:
                    print("No data received")
            except Exception as e:
                print(f"Error: {e}")
            
            # Close the ELM327 driver
            await elm.close()
            print("\n=== Connection closed ===")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
