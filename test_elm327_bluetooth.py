#!/usr/bin/env python3
"""
Test ELM327 communication over Bluetooth RFCOMM connection.
"""

import serial
import time
import pytest
import os

def test_elm327_bluetooth(port='/dev/rfcomm0', baudrate=115200):
    """Test ELM327 commands over Bluetooth."""
    # Skip test if the device doesn't exist (no hardware connected)
    if not os.path.exists(port):
        pytest.skip(f"Device {port} not found - skipping hardware test")
    
    print(f"\n{'='*80}")
    print("🧪 Testing ELM327 Communication over Bluetooth")
    print(f"{'='*80}\n")
    
    try:
        # Open the serial port
        print(f"📡 Opening {port} at {baudrate} baud...")
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=2,
            write_timeout=2
        )
        
        if not ser.is_open:
            print(f"❌ Failed to open {port}")
            assert False, f"Failed to open {port}"
            
        print(f"✅ Port opened successfully\n")
        
        # Wait a moment for the connection to stabilize
        time.sleep(0.5)
        
        # Test commands
        commands = [
            ("ATZ", "Reset adapter"),
            ("ATE0", "Echo off"),
            ("ATL0", "Line feeds off"),
            ("ATH1", "Headers on"),
            ("ATSP0", "Auto protocol"),
            ("0100", "Request supported PIDs"),
        ]
        
        for cmd, description in commands:
            print(f"📤 Sending: {cmd} ({description})")
            
            # Clear any pending data
            ser.reset_input_buffer()
            
            # Send command
            ser.write((cmd + '\r').encode('ascii'))
            ser.flush()
            
            # Read response
            response = b''
            start_time = time.time()
            
            while True:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    response += chunk
                    
                # Check for prompt character '>'
                if b'>' in response:
                    break
                    
                # Timeout after 2 seconds
                if time.time() - start_time > 2:
                    print(f"   ⚠️  Timeout waiting for response")
                    break
                    
                time.sleep(0.05)
            
            # Display response
            response_str = response.decode('ascii', errors='replace').strip()
            if response_str:
                print(f"📥 Response: {response_str}")
                print()
            else:
                print(f"   ❌ No response received\n")
        
        ser.close()
        print(f"{'='*80}")
        print("✅ Test completed successfully!")
        print(f"{'='*80}\n")
        
    except serial.SerialException as e:
        print(f"\n❌ Serial error: {e}")
        assert False, f"Serial error: {e}"
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        assert False, f"Unexpected error: {e}"

if __name__ == "__main__":
    import sys
    
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/rfcomm0'
    
    print("\n" + "="*80)
    print("Make sure the RFCOMM connection is established:")
    print("  sudo rfcomm connect /dev/rfcomm0 00:1D:A5:1E:32:25 1 &")
    print("="*80)
    
    try:
        test_elm327_bluetooth(port)
        sys.exit(0)
    except (AssertionError, Exception):
        sys.exit(1)

