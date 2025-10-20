# Connection Layer Implementation

This document describes the connection abstraction layer for OBD2 communication.

## Overview

The connection layer provides an abstract interface for communicating with OBD2 adapters through different physical connections (Serial, Bluetooth, etc.). This design separates the communication protocol (ELM327) from the physical connection mechanism.

**Note:** The term "connection" is used instead of "transport" to avoid confusion with ISO-TP (ISO Transport Protocol), which is a different concept used at the protocol level.

## Architecture

```
┌─────────────────────────────────────────┐
│           Application Code              │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│         ELM327 Driver                   │
│  (Protocol implementation)              │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│       Connection Interface              │
│         (Abstract Base)                 │
└──────────┬──────────────────┬───────────┘
           │                  │
┌──────────▼─────────┐   ┌───▼────────────┐
│  SerialConnection  │   │ BluetoothConn. │
│   (USB/Serial)     │   │   (RFCOMM)     │
└────────────────────┘   └────────────────┘
```

## Components

### 1. Connection (Abstract Base Class)

**File:** `driver/connection.py`

Defines the abstract interface that all connection implementations must follow:

```python
class Connection(ABC):
    async def open() -> None
    async def close() -> None
    async def write(data: bytes) -> None
    async def read(size: int) -> bytes
    async def read_until(terminator: bytes, timeout: Optional[float]) -> bytes
    async def flush_input() -> None
    async def flush_output() -> None
```

**Exceptions:**
- `ConnectionException`: Base exception for connection errors
- `ConnectionTimeoutError`: Timeout during connection operation
- `ConnectionError`: Error during connection operation

### 2. SerialConnection

**File:** `driver/serial_connection.py`

Implements serial port communication (USB/Serial adapters).

**Features:**
- pyserial-based implementation
- Async I/O using `asyncio.run_in_executor()`
- Static method `list_ports()` for port discovery
- Supports standard serial parameters (baudrate, timeout, etc.)

**Example:**
```python
from driver import ELM327, SerialConnection

connection = SerialConnection('/dev/ttyUSB0', baudrate=38400)
async with connection:
    elm = ELM327(connection)
    await elm.initialize()
    response = await elm.send_message(None, 0x0D)
```

### 3. BluetoothConnection

**File:** `driver/bluetooth_connection.py`

Implements Bluetooth Classic communication using RFCOMM.

**Features:**
- RFCOMM binding to `/dev/rfcomm<N>` devices
- Automatic pairing check via `bluetoothctl`
- Static async method `discover_devices()` for Bluetooth scanning
- Supports custom RFCOMM channel and baudrate
- Automatic cleanup of RFCOMM bindings

**Example:**
```python
from driver import ELM327, BluetoothConnection

connection = BluetoothConnection(
    address="00:1D:A5:1E:32:25",
    rfcomm_device=0,  # Uses /dev/rfcomm0
    channel=1,
    baudrate=115200
)
async with connection:
    elm = ELM327(connection)
    await elm.initialize()
    response = await elm.send_message(None, 0x0D)
```

## ELM327 Driver Integration

### Changes to ELM327

The `ELM327` class now accepts a `Connection` instance instead of creating its own serial connection:

**Old API:**
```python
elm = ELM327(port='/dev/ttyUSB0', baudrate=38400)
```

**New API:**
```python
connection = SerialConnection('/dev/ttyUSB0', baudrate=38400)
async with connection:
    elm = ELM327(connection)
    await elm.initialize()
```

### Key Changes

1. **Constructor:** `__init__(self, connection: Connection)`
   - Takes a Connection instance instead of port/baudrate parameters
   
2. **Initialization:** `async def initialize()`
   - Must be called after connection is opened
   - Configures ELM327 with optimal settings
   
3. **Async API:** All I/O operations are now async
   - `await elm.initialize()`
   - `await elm.send_message(can_id, pid)`
   - `await elm.close()`

## Usage Examples

### Serial Connection Example

```python
import asyncio
from driver import ELM327, SerialConnection

async def main():
    connection = SerialConnection('/dev/ttyUSB0', baudrate=38400)
    
    async with connection:
        elm = ELM327(connection)
        await elm.initialize()
        
        # Read vehicle speed
        response = await elm.send_message(None, 0x0D)
        speed = response.data[0] if response.data else 0
        print(f"Speed: {speed} km/h")
        
        await elm.close()

asyncio.run(main())
```

### Bluetooth Connection Example

```python
import asyncio
from driver import ELM327, BluetoothConnection

async def main():
    connection = BluetoothConnection(
        address="00:1D:A5:1E:32:25",
        rfcomm_device=0,
        channel=1,
        baudrate=115200
    )
    
    async with connection:
        elm = ELM327(connection)
        await elm.initialize()
        
        # Read engine RPM
        response = await elm.send_message(None, 0x0C)
        if response.data and len(response.data) >= 2:
            rpm = ((response.data[0] * 256) + response.data[1]) / 4
            print(f"RPM: {rpm}")
        
        await elm.close()

asyncio.run(main())
```

## Benefits

1. **Separation of Concerns:** Protocol logic (ELM327) is independent of physical connection
2. **Testability:** Easy to create mock connections for testing
3. **Extensibility:** New connection types can be added without modifying ELM327
4. **Flexibility:** Applications can choose the appropriate connection at runtime
5. **Resource Management:** Proper async context managers ensure cleanup

## Migration Guide

### For Existing Code

**Before:**
```python
from driver import ELM327

elm = ELM327(port='/dev/ttyUSB0', baudrate=38400)
response = elm.send_message(None, 0x0D)
elm.close()
```

**After:**
```python
import asyncio
from driver import ELM327, SerialConnection

async def main():
    connection = SerialConnection('/dev/ttyUSB0', baudrate=38400)
    async with connection:
        elm = ELM327(connection)
        await elm.initialize()
        response = await elm.send_message(None, 0x0D)
        await elm.close()

asyncio.run(main())
```

### Key Changes

1. Import `SerialConnection` or `BluetoothConnection`
2. Create a connection instance separately
3. Use async/await syntax
4. Call `initialize()` after connection is opened
5. Use async context manager (`async with`) for proper cleanup

## Testing

Connection implementations can be tested independently:

```python
# Test serial connection
connection = SerialConnection('/dev/ttyUSB0')
async with connection:
    await connection.write(b'ATZ\r')
    response = await connection.read(100)
    print(response)

# Test Bluetooth connection
connection = BluetoothConnection('00:1D:A5:1E:32:25')
async with connection:
    await connection.write(b'ATZ\r')
    response = await connection.read(100)
    print(response)
```

Mock connections can be created for unit testing:

```python
class MockConnection(Connection):
    async def open(self):
        self._is_open = True
    
    async def close(self):
        self._is_open = False
    
    async def write(self, data: bytes):
        # Simulate write
        pass
    
    async def read(self, size: int) -> bytes:
        # Return mock data
        return b'OK\r'
```

## Future Extensions

Potential future connection implementations:

- **WiFi Connection:** For WiFi OBD2 adapters
- **Network Connection:** TCP/IP sockets for remote adapters
- **USB HID Connection:** Direct USB communication
- **CAN Connection:** Direct CAN bus access via SocketCAN

Each can be implemented by extending the `Connection` base class.
