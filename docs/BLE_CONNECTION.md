# BLE Connection Driver for OBD2 Adapters

This driver provides Bluetooth Low Energy (BLE) support for OBD2 adapters, specifically tested with the **Vgate iCar Pro BLE 4.0** adapter.

## Features

- ✅ **Synchronous API**: Thread-safe wrapper around async BLE operations
- ✅ **Auto-discovery**: Scan for nearby OBD2 BLE devices
- ✅ **ELM327 Compatible**: Works seamlessly with the existing ELM327 protocol layer
- ✅ **Connection abstraction**: Implements the same interface as Serial and Bluetooth RFCOMM connections

## Supported Devices

### Tested Devices
- **Vgate iCar Pro BLE 4.0** (Amazon: B071D8SYXN)
  - Device Name: IOS-Vlink
  - Service UUID: `e7810a71-73ae-499d-8c15-faa9aef0c3f2`
  - Characteristic UUID: `bef8d6c9-9c21-4c9e-b632-bd58c1009f9f`
  - ELM327 Version: v2.3

### Potentially Compatible Devices
Any ELM327-compatible BLE adapter should work, including:
- Vgate iCar series
- Generic ELM327 BLE 4.0 adapters
- Other adapters using standard BLE serial service

## Requirements

```bash
pip install bleak
```

## Quick Start

### 1. Discover OBD2 Devices

```python
from driver import BLEConnection

# Scan for OBD2 BLE devices
devices = BLEConnection.discover_obd_devices(timeout=10.0)

for device in devices:
    print(f"{device['name']} - {device['address']}")
```

### 2. Connect to a Device

```python
from driver import BLEConnection, ELM327

# Connect to device by MAC address
conn = BLEConnection(address="D2:E0:2F:8D:5C:6B", timeout=10.0)
conn.open()

# Use with ELM327 protocol
elm = ELM327(connection=conn)
elm.initialize()

# Send commands
version = elm._send_command("ATI")
print(f"Version: {version}")

# Close connection
elm.close()
```

### 3. Run the Example

```bash
python examples/ble_example.py
```

## API Reference

### BLEConnection Class

```python
class BLEConnection(Connection):
    def __init__(
        self,
        address: str,
        timeout: float = 10.0,
        service_uuid: Optional[str] = None,
        notify_uuid: Optional[str] = None,
        write_uuid: Optional[str] = None,
    )
```

**Parameters:**
- `address`: BLE device MAC address (e.g., "D2:E0:2F:8D:5C:6B")
- `timeout`: Connection and read/write timeout in seconds
- `service_uuid`: Optional specific service UUID (auto-detected if not provided)
- `notify_uuid`: Optional notify characteristic UUID (auto-detected if not provided)
- `write_uuid`: Optional write characteristic UUID (auto-detected if not provided)

**Methods:**
- `open()`: Open the BLE connection
- `close()`: Close the BLE connection
- `write(data: bytes)`: Write data to the device
- `read(size: int)`: Read specified number of bytes
- `read_until(terminator: bytes, timeout: Optional[float])`: Read until terminator found
- `flush_input()`: Clear input buffer
- `flush_output()`: No-op for BLE

**Static Methods:**
- `discover_devices(timeout: float, name_filter: Optional[str])`: Discover all BLE devices
- `discover_obd_devices(timeout: float)`: Discover OBD2 BLE devices

## Implementation Details

### Thread-Safe Design

The driver uses a background thread to run the asyncio event loop, providing a synchronous API that's compatible with the existing connection interface. This means:

- No need to use `async/await` in your code
- Works with existing blocking code
- Thread-safe buffer management
- Automatic event loop lifecycle management

### Characteristic Discovery

The driver automatically discovers the correct GATT characteristics:

1. Searches for notify/indicate characteristics (for receiving data)
2. Searches for write characteristics (for sending data)
3. Prefers characteristics that support both operations
4. Falls back to manual specification via constructor parameters

### Data Buffering

- Incoming BLE notifications are buffered in a thread-safe bytearray
- `read()` and `read_until()` pull data from the buffer
- Automatic timeout handling
- No busy-waiting (uses small sleep intervals)

## Testing

The driver includes comprehensive test scripts:

### Quick Test (Known Device)
```bash
python test_ble_quick.py
```

### Full Test Suite
```bash
python test_ble_driver.py
```

### Manual Connection Test
```bash
python test_vgate_icar_pro.py
```

## Troubleshooting

### Device Not Found

**Problem:** `discover_obd_devices()` returns empty list

**Solutions:**
1. Ensure the dongle is connected to 12V power
2. Check if the LED is blinking (pairing mode)
3. Move closer to the dongle (BLE range is limited)
4. Restart the dongle by unplugging and replugging

### Connection Timeout

**Problem:** `ConnectionError: Failed to connect`

**Solutions:**
1. Device may be connected to another device (phone, car)
2. Device may be in sleep mode (needs car ignition on)
3. Bluetooth may be disabled on your system
4. Try increasing the timeout: `BLEConnection(address, timeout=20.0)`

### No Response from Commands

**Problem:** Commands sent but no response received

**Solutions:**
1. Ensure `conn.open()` was called before creating ELM327
2. Check if the dongle is connected to a car (some commands require vehicle)
3. Increase timeout for slow responses
4. Verify the dongle supports ELM327 protocol

## Comparison with RFCOMM Bluetooth

| Feature | BLE (ble_connection.py) | RFCOMM (bluetooth_connection.py) |
|---------|------------------------|-----------------------------------|
| Protocol | Bluetooth 4.0+ (BLE) | Bluetooth 2.0 (Classic) |
| Power Usage | Very Low | Higher |
| Range | ~50m | ~100m |
| Pairing | Often not required | Required |
| Speed | Lower latency | Higher throughput |
| Setup | Auto-discovery | May need `rfcomm bind` |

## Architecture

```
┌─────────────────────────────────────────┐
│         BLEConnection                   │
│  (Synchronous API)                      │
├─────────────────────────────────────────┤
│  - Thread-safe buffer                   │
│  - Background event loop thread         │
│  - Coroutine runner                     │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│         BleakClient                     │
│  (Async BLE Library)                    │
├─────────────────────────────────────────┤
│  - GATT service discovery               │
│  - Characteristic read/write            │
│  - Notification handling                │
└──────────┬──────────────────────────────┘
           │
           ▼
     System Bluetooth
       (BlueZ/Windows)
```

## Future Enhancements

- [ ] Add connection state monitoring
- [ ] Implement automatic reconnection
- [ ] Support for multiple simultaneous connections
- [ ] Better MTU negotiation
- [ ] Connection parameter optimization
- [ ] Support for BLE security features

## Credits

- Developed for the obd2_tool project
- Tested with Vgate iCar Pro BLE 4.0 adapter
- Uses the excellent [bleak](https://github.com/hbldh/bleak) library for BLE support
