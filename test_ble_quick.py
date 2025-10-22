#!/usr/bin/env python3
"""
Quick test of BLE connection with ELM327 protocol.
Uses the known IOS-Vlink address.
"""

from driver.ble_connection import BLEConnection
from driver.elm327 import ELM327

# Known IOS-Vlink address from previous scans
VGATE_ADDRESS = "D2:E0:2F:8D:5C:6B"

print("=" * 80)
print("🧪 Quick BLE + ELM327 Test")
print("=" * 80)
print(f"\nConnecting to: {VGATE_ADDRESS}\n")

try:
    # Create and open BLE connection
    print("📡 Opening BLE connection...")
    conn = BLEConnection(address=VGATE_ADDRESS, timeout=10.0)
    conn.open()
    print("✅ Connected\n")
    
    # Create ELM327 protocol handler
    elm = ELM327(connection=conn)
    
    # Initialize
    print("🔧 Initializing ELM327...")
    elm.initialize()
    print("✅ Initialized\n")
    
    # Get version
    print("📤 Getting version (ATI)...")
    version = elm._send_command("ATI")
    print(f"✅ Version: {version}\n")
    
    # Get voltage
    print("📤 Getting voltage (ATRV)...")
    try:
        voltage = elm._send_command("ATRV")
        print(f"✅ Voltage: {voltage}\n")
    except Exception as e:
        print(f"⚠️  Voltage query failed: {e}\n")
    
    # Close
    elm.close()
    print("✅ Connection closed")
    
    print("\n" + "=" * 80)
    print("✅ Test completed successfully!")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
