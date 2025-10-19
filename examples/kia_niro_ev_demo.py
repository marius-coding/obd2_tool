#!/usr/bin/env python3
"""
Example script demonstrating Kia Niro EV diagnostic interface.

This script connects to a Kia Niro EV via ELM327 adapter and reads
various battery and vehicle parameters.
"""

import sys
import os

# Add parent directory to path to import driver module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from driver.elm327 import ELM327
from driver.kia_niro_ev import KiaNiroEV
from driver.mock_serial import MockSerial


def main():
    """Main function to demonstrate Kia Niro EV diagnostics."""
    
    print("Kia Niro EV Diagnostic Tool")
    print("=" * 50)
    
    # Check if we should use mock serial
    use_mock = '--mock' in sys.argv or len(sys.argv) == 1  # Default to mock if no args
    
    # Connect to ELM327 (auto-detects port or uses mock)
    print("\nConnecting to ELM327...")
    try:
        if use_mock:
            print("Using MockSerial (simulated data)")
            mock_serial = MockSerial(port="mock", baudrate=38400, timeout=1.0)
            elm = ELM327(serial_connection=mock_serial)
            print(f"✓ Connected to mock device")
        else:
            elm = ELM327()
            print(f"✓ Connected on port: {elm.port}")
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
        
        # Read battery voltage and current
        voltage = kia.get_battery_voltage()
        current = kia.get_battery_current()
        power = voltage * current / 1000  # kW
        print(f"Battery Voltage: {voltage:.1f}V")
        print(f"Battery Current: {current:.1f}A")
        print(f"Power: {power:.1f}kW {'(charging)' if current < 0 else '(discharging)'}")
        
        # Read cell voltages
        print("\n--- Cell Voltage Statistics ---")
        max_v, max_cell = kia.get_max_cell_voltage()
        min_v, min_cell = kia.get_min_cell_voltage()
        print(f"Maximum Cell: {max_v:.3f}V (Cell #{max_cell})")
        print(f"Minimum Cell: {min_v:.3f}V (Cell #{min_cell})")
        print(f"Voltage Difference: {(max_v - min_v)*1000:.1f}mV")
        
        # Read State of Health
        print("\n--- Battery Health ---")
        soh = kia.get_soh()
        print(f"State of Health: {soh:.1f}%")
        
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
        
        # Optional: Read specific cell voltages
        print("\n--- Sample Cell Voltages ---")
        for cell_num in [1, 25, 50, 75, 98]:
            cell_v = kia.get_cell_voltage(cell_num)
            print(f"Cell {cell_num:2d}: {cell_v:.3f}V")
        
    except Exception as e:
        print(f"\n✗ Error reading data: {e}")
    
    finally:
        # Close connection
        print("\nClosing connection...")
        elm.close()
        print("✓ Done")


if __name__ == "__main__":
    main()
