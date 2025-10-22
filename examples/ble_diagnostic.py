#!/usr/bin/env python3
"""
BLE Diagnostic Script for ELM327 adapters.

This script tests basic ELM327 communication over BLE before attempting
Kia-specific UDS commands. Useful for debugging connection issues.
"""

import sys
import os
import time

# Add parent directory to path to import driver module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from driver.ble_connection import BLEConnection
from driver.elm327 import ELM327


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    """Run BLE diagnostic tests."""
    
    print("BLE ELM327 Diagnostic Tool")
    print("="*60)
    
    # Get BLE address from command line or discover
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
    
    # Discover if no address provided
    if not address:
        print("\nNo address supplied, scanning for OBD devices (5s)...")
        devices = BLEConnection.discover_obd_devices(timeout=5.0)
        if not devices:
            print("✗ No OBD BLE devices found.")
            print("\nTry passing --address <MAC> or -a <MAC>")
            return 1
        
        # Show all discovered devices
        print(f"\nDiscovered {len(devices)} device(s):")
        for i, dev in enumerate(devices, 1):
            print(f"  {i}. {dev['name']} @ {dev['address']}")
        
        # Pick the first one
        picked = devices[0]
        address = picked['address']
        print(f"\nUsing: {picked['name']} @ {address}")
    
    # Connect to BLE device
    print_section("Step 1: BLE Connection")
    try:
        print(f"Connecting to {address}...")
        conn = BLEConnection(address=address, timeout=15.0)  # Longer timeout
        conn.open()
        print("✓ BLE connection established")
    except Exception as e:
        print(f"✗ BLE connection failed: {e}")
        return 1
    
    # Initialize ELM327
    print_section("Step 2: ELM327 Initialization")
    try:
        elm = ELM327(conn)
        print("Initializing ELM327 (sending AT commands)...")
        elm.initialize()
        print("✓ ELM327 initialized successfully")
    except Exception as e:
        print(f"✗ ELM327 initialization failed: {e}")
        conn.close()
        return 1
    
    # Test basic AT commands
    print_section("Step 3: Basic AT Commands")
    test_commands = [
        ('AT I', 'Device identification'),
        ('AT RV', 'Read voltage'),
        ('AT DP', 'Describe protocol'),
    ]
    
    for cmd, desc in test_commands:
        try:
            print(f"\nSending: {cmd} ({desc})")
            response = elm._send_command(cmd)
            print(f"Response: {response[:100]}")  # Truncate long responses
            print("✓ Success")
        except Exception as e:
            print(f"✗ Failed: {e}")
    
    # Test OBD-II standard PID
    print_section("Step 4: Standard OBD-II Request")
    try:
        print("\nTrying standard OBD-II request (Mode 01 PID 0C - Engine RPM)...")
        print("Sending: 010C")
        response = elm._send_command('010C')
        print(f"Response: {response[:100]}")
        print("✓ OBD-II request completed")
        
        if 'NO DATA' in response:
            print("⚠ Note: ECU returned NO DATA (expected if engine off or not connected to vehicle)")
        elif 'ERROR' in response or '?' in response:
            print("⚠ Note: ECU returned error (expected if not connected to vehicle)")
    except Exception as e:
        print(f"✗ OBD-II request failed: {e}")
    
    # Test UDS request to BMS
    print_section("Step 5: UDS Request to BMS")
    try:
        print("\nSetting CAN header to 7E4 (Kia BMS)...")
        elm._send_command('ATSH7E4')
        print("✓ Header set")
        
        print("\nWaiting 2 seconds for ECU wake-up...")
        time.sleep(2.0)
        
        print("\nSending UDS request: 220101 (Read BMS main data)...")
        response = elm._send_command('220101')
        print(f"Response length: {len(response)} chars")
        print(f"Response: {response[:200]}")  # Show first 200 chars
        print("✓ UDS request completed")
        
        # Analyze response
        if 'NO DATA' in response:
            print("\n⚠ Analysis: ECU returned NO DATA")
            print("   Possible causes:")
            print("   - Vehicle ignition is off")
            print("   - Not connected to vehicle CAN bus")
            print("   - Incorrect CAN ID for this vehicle")
        elif 'ERROR' in response or '?' in response:
            print("\n⚠ Analysis: ELM327 returned error")
            print("   Possible causes:")
            print("   - Incorrect command format")
            print("   - Protocol not initialized")
        elif '7EC' in response:
            print("\n✓ Analysis: Received response from ECU (7EC)")
            print("   This is the expected BMS response ID!")
            
            # Count frames
            frame_count = response.count('7EC')
            print(f"   Received {frame_count} frame(s)")
            
            if frame_count >= 5:
                print("   ✓ Multi-frame response looks complete")
            else:
                print("   ⚠ Fewer frames than expected (might be incomplete)")
        else:
            print("\n? Analysis: Unexpected response format")
    except Exception as e:
        print(f"✗ UDS request failed: {e}")
    
    # Summary
    print_section("Summary")
    print("\nDiagnostic test completed.")
    print("\nIf all steps passed, your BLE connection is working correctly.")
    print("If UDS requests fail, try:")
    print("  1. Ensure vehicle ignition is ON")
    print("  2. Wait longer for ECU wake-up (increase sleep time)")
    print("  3. Verify the CAN ID is correct for your vehicle")
    print("  4. Check if a security/authentication session is needed")
    
    # Cleanup
    print("\nClosing connection...")
    elm.close()
    print("✓ Done")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
