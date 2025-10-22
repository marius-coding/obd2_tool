#!/usr/bin/env python3
"""
Example script demonstrating Kia Niro EV diagnostic interface.

This script connects to a Kia Niro EV via ELM327 adapter and reads
various battery and vehicle parameters.
"""

import sys
import os
import time

# Add parent directory to path to import driver module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from driver.elm327 import ELM327
from driver.kia_niro_ev import KiaNiroEV
from driver.ble_connection import BLEConnection
from driver.mock_serial import MockConnection


def main():
    """Main function to demonstrate Kia Niro EV diagnostics."""
    
    print("Kia Niro EV Diagnostic Tool")
    print("=" * 50)
    
    # CLI options: --mock to force simulated device, --address <addr> to use a specific BLE address
    use_mock = '--mock' in sys.argv

    # Try to get address from --address or -a
    address = None
    if '--address' in sys.argv:
        try:
            address = sys.argv[sys.argv.index('--address') + 1]
        except IndexError:
            address = None
    elif '-a' in sys.argv:
        try:
            address = sys.argv[sys.argv.index('-a') + 1]
        except IndexError:
            address = None

    # Connect to ELM327 via BLE (default) or mock if requested
    print("\nConnecting to ELM327...")
    try:
        if use_mock:
            print("Using MockConnection (simulated data)")
            mock_conn = MockConnection()
            # open mock connection and initialize ELM327
            mock_conn.open()
            elm = ELM327(mock_conn)
            elm.initialize()
            print(f"✓ Connected to mock device")
        else:
            # Use BLE by default
            if not address:
                print("No address supplied, scanning for OBD devices (5s)...")
                devices = BLEConnection.discover_obd_devices(timeout=5.0)
                if not devices:
                    print("✗ No OBD BLE devices found. Try passing --address <MAC> or use --mock for simulated data.")
                    return
                # Pick the first discovered device
                picked = devices[0]
                address = picked['address']
                print(f"Discovered device: {picked['name']} @ {address}")

            print(f"Opening BLE connection to {address}...")
            conn = BLEConnection(address=address, timeout=10.0)
            conn.open()
            elm = ELM327(conn)
            elm.initialize()
            print(f"✓ Connected to BLE device: {address}")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return
    
    # Create Kia Niro EV interface
    kia = KiaNiroEV(elm)
    
    try:
        # Read State of Charge
        print("\n--- Battery Status ---")
        soc = kia.get_soc()
        print(f"State of Charge: {soc:.1f}%")
        
        # Small delay between requests to give ECU time to respond
        time.sleep(0.3)
        
        # Read battery voltage and current
        voltage = kia.get_battery_voltage()
        time.sleep(0.3)
        
        current = kia.get_battery_current()
        time.sleep(0.3)
        
        power = voltage * current / 1000  # kW
        print(f"Battery Voltage: {voltage:.1f}V")
        print(f"Battery Current: {current:.1f}A")
        print(f"Power: {power:.1f}kW {'(charging)' if current < 0 else '(discharging)'}")
        
        # Read cell voltages
        print("\n--- Cell Voltage Statistics ---")
        max_v, max_cell = kia.get_max_cell_voltage()
        time.sleep(0.3)
        
        min_v, min_cell = kia.get_min_cell_voltage()
        time.sleep(0.3)
        
        print(f"Maximum Cell: {max_v:.3f}V (Cell #{max_cell})")
        print(f"Minimum Cell: {min_v:.3f}V (Cell #{min_cell})")
        print(f"Voltage Difference: {(max_v - min_v)*1000:.1f}mV")
        
        # Read State of Health
        print("\n--- Battery Health ---")
        soh = kia.get_soh()
        print(f"State of Health: {soh:.1f}%")
        time.sleep(0.3)
        
        # Read temperatures
        print("\n--- Battery Temperatures ---")
        temps = kia.get_battery_temperatures()
        print(f"Maximum: {temps['max']}°C")
        print(f"Minimum: {temps['min']}°C")
        print(f"Inlet: {temps['inlet']}°C")
        print(f"Module 1: {temps['module_01']}°C")
        print(f"Module 2: {temps['module_02']}°C")
        print(f"Module 3: {temps['module_03']}°C")
        print(f"Module 4: {temps['module_04']}°C")
        time.sleep(0.3)
        
        # Optional: Read specific cell voltages
        print("\n--- Sample Cell Voltages ---")
        for cell_num in [1, 25, 50, 75, 98]:
            cell_v = kia.get_cell_voltage(cell_num)
            print(f"Cell {cell_num:2d}: {cell_v:.3f}V")
            time.sleep(0.3)  # Delay between cell voltage reads
        
    except Exception as e:
        print(f"\n✗ Error reading data: {e}")
    
    finally:
        # Close connection
        print("\nClosing connection...")
        elm.close()
        print("✓ Done")


if __name__ == "__main__":
    main()
