# Bluetooth Adapter Support - Testing & Implementation Plan

## Current Status

### Adapters Identified on System

1. **OBDII** (00:1D:A5:1E:32:25)
   - Paired: ✅ Yes
   - Bonded: ✅ Yes
   - Protocol: Classic Bluetooth 2.0
   - UUID: Serial Port (00001101...)
   - Status: Disconnected (requires power from car or 12V source)

2. **Android-Vlink** (13:E0:2F:8D:5C:6B)
   - Paired: ✅ Yes
   - Bonded: ✅ Yes
   - Protocol: Unclear (likely classic Bluetooth or BLE)
   - Status: Disconnected (requires power from car)

3. **Vgate iCar Pro BLE 4.0** (from Amazon link B071D8SYXN)
   - Protocol: Bluetooth Low Energy (BLE 4.0)
   - Not currently connected/available in scan

## Connection Details

Both adapters use the **Serial Port Profile (RFCOMM)** for OBD2 communication, which means:
- They appear as serial ports (`/dev/rfcomm0`, `/dev/rfcomm1`, etc.) when connected
- Communication is done via standard serial port reading/writing
- ELM327 protocol commands work over the serial port

## Test Scripts Created

### 1. `test_bluetooth_connection.py`
- Scans for Bluetooth LE devices
- Useful for testing Bluetooth 4.0 adapters like Vgate iCar Pro

### 2. `test_bluetooth_direct.py`
- Tests connection to known paired BLE devices
- Uses bleak library

### 3. `test_bluetooth_rfcomm.py` (for classic Bluetooth)
- Uses bluetoothctl to connect
- Binds RFCOMM ports
- Tests serial port communication
- Uses `pyserial` for actual data transfer

## Implementation Plan

### Phase 1: Bluetooth Adapter Support (Classic Bluetooth 2.0)

**File**: `driver/bluetooth.py`

```python
class BluetoothAdapter:
    def __init__(self, address: str, port: int = 0):
        """
        Initialize Bluetooth adapter.
        
        Args:
            address: MAC address of OBD2 adapter (e.g., "00:1D:A5:1E:32:25")
            port: RFCOMM port (0-30, auto-assigned by default)
        """
        self.address = address
        self.port = port
        self._serial = None
        
    async def connect(self) -> None:
        """Connect to the Bluetooth adapter."""
        # 1. Use bluetoothctl to connect to address
        # 2. Bind RFCOMM port
        # 3. Open /dev/rfcomm<port> with PySerial
        
    async def disconnect(self) -> None:
        """Disconnect from the adapter."""
        
    async def send_command(self, command: str) -> str:
        """Send ELM327 command and read response."""
        
    async def close(self) -> None:
        """Close the connection."""
```

### Phase 2: Unified Interface

Modify `driver/__init__.py` to support both serial and Bluetooth:

```python
from .elm327 import ELM327Protocol
from .isotp import ISOTPHandler
from .bluetooth import BluetoothAdapter

class OBD2Manager:
    @classmethod
    async def from_port(cls, port: str, protocol: str = "elm327"):
        """Connect via serial port"""
        
    @classmethod
    async def from_bluetooth(cls, address: str, protocol: str = "elm327"):
        """Connect via Bluetooth"""
```

### Phase 3: Testing

Update tests to cover:
- Bluetooth device discovery
- Connection/disconnection
- Command send/receive over Bluetooth
- Error handling for disconnected devices

## Dependencies

Already installed:
- ✅ `pyserial` (3.5)
- ✅ `bleak` (1.1.1) for BLE testing

Additional dependencies needed:
- `pybluez` (optional, for advanced Bluetooth operations)
- System: `bluetooth`, `bluez` packages

## Next Steps

1. **Power up the NK Mini EKN327 adapter** with 12V
2. **Test the RFCOMM connection manually**:
   ```bash
   sudo bluetoothctl connect 00:1D:A5:1E:32:25
   sudo rfcomm bind /dev/rfcomm0 00:1D:A5:1E:32:25
   cat /dev/rfcomm0  # Should see Bluetooth device ready
   ```

3. **Implement `driver/bluetooth.py`** with the BluetoothAdapter class
4. **Create `driver/bluetooth_discovery.py`** for device scanning
5. **Update tests** in `tests/test_bluetooth.py`
6. **Create example** in `examples/bluetooth_demo.py`

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│         OBD2Manager (Unified Interface)             │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌───────────────────┐    ┌───────────────────┐   │
│  │  SerialAdapter    │    │ BluetoothAdapter  │   │
│  │ (existing)        │    │ (new)             │   │
│  └────────┬──────────┘    └────────┬──────────┘   │
│           │                        │              │
└───────────┼────────────────────────┼──────────────┘
            │                        │
            ▼                        ▼
      /dev/ttyUSB0           /dev/rfcomm<N>
      /dev/ttyACM0           (Bluetooth RFCOMM)
      (Serial Ports)
```

## Notes

- Bluetooth Classic (2.0) uses RFCOMM for serial emulation
- BLE (4.0+) requires different handling (already have `bleak` for this)
- Some cars may have multiple OBD2 protocols; adapters handle protocol detection
- Power consumption is critical for always-on adapters (sleep mode in BLE 4.0)
