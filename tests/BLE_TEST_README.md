# BLE Connection Test Suite

This directory contains comprehensive tests for the BLE (Bluetooth Low Energy) connection driver.

## Test Files

### `test_ble_connection.py` - Unit Tests (No Hardware Required)
Mocked unit tests that verify the BLEConnection class behavior without requiring actual BLE hardware.

**Test Coverage:**
- ✅ Initialization with/without bleak library
- ✅ Connection state management
- ✅ Parameter validation
- ✅ Buffer operations (read/write)
- ✅ Timeout handling
- ✅ Notification handler
- ✅ Device discovery (mocked)
- ✅ Error handling for closed connections
- ✅ Data buffering and chunking

**Run with:**
```bash
python -m pytest tests/test_ble_connection.py -v
```

**22 tests** - All can run without hardware

---

### `test_ble_real.py` - Integration Tests (Hardware Required)
Real hardware integration tests that verify communication with an actual BLE OBD2 adapter.

**Requirements:**
- Vgate iCar Pro (or compatible) BLE adapter powered on
- Adapter address configured in test file (default: `D2:E0:2F:8D:5C:6B`)
- Adapter does NOT need to be connected to a vehicle

**Test Coverage:**
- ✅ BLE connection establishment
- ✅ GATT characteristic discovery
- ✅ ELM327 initialization over BLE
- ✅ Version query (ATI command)
- ✅ Voltage reading (ATRV command)
- ✅ Multiple sequential commands
- ✅ Connection/reconnection
- ✅ Device discovery (real scan)
- ✅ Error handling (no vehicle connected)
- ✅ Buffer management with real data

**Run with:**
```bash
python -m pytest tests/test_ble_real.py -v
```

**8 tests** - Requires BLE hardware

---

## Test Markers

Tests use pytest markers for organization:

- `@pytest.mark.integration` - Integration tests requiring hardware
- `@pytest.mark.ble` - Tests requiring BLE adapter

**Run only integration tests:**
```bash
python -m pytest -m integration
```

**Run only BLE tests:**
```bash
python -m pytest -m ble
```

**Run all BLE tests:**
```bash
python -m pytest tests/test_ble*.py -v
```

---

## Test Configuration

### Update BLE Device Address
Edit `tests/test_ble_real.py` to match your device:

```python
BLE_ADDRESS = "D2:E0:2F:8D:5C:6B"  # Your device MAC address
```

Find your device address by running:
```bash
python -c "from driver import BLEConnection; print(BLEConnection.discover_obd_devices())"
```

### Timeout Settings
Some tests use longer timeouts for BLE (15 seconds). Adjust if needed:

```python
CONNECTION_TIMEOUT = 15.0  # Increase for slower connections
```

---

## Test Results Summary

### Unit Tests (`test_ble_connection.py`)
```
22 tests - All PASSED ✅
Runtime: ~0.35 seconds
Hardware Required: No
```

**Coverage:**
- Initialization and configuration
- Connection state management  
- Read/write operations
- Buffer management
- Timeout handling
- Device discovery
- Error conditions

### Integration Tests (`test_ble_real.py`)
```
8 tests - 7 PASSED ✅, 1 SKIPPED ⏭️
Runtime: ~74 seconds (depends on BLE connection speed)
Hardware Required: Yes (BLE OBD2 adapter)
```

**Tests Skipped:**
- `test_elm327_no_vehicle_connection` - Only when adapter is connected to vehicle

**Coverage:**
- Real BLE connection
- GATT service discovery
- ELM327 protocol over BLE
- Command/response handling
- Connection lifecycle
- Real-world buffer handling

---

## Continuous Integration

### Running All Tests
```bash
# Run all tests (unit + integration)
python -m pytest tests/ -v

# Run only unit tests (fast, no hardware)
python -m pytest tests/test_ble_connection.py -v

# Run with coverage
python -m pytest tests/test_ble*.py --cov=driver.ble_connection --cov-report=html
```

### CI/CD Considerations

For CI pipelines without BLE hardware:
```bash
# Run only unit tests
python -m pytest tests/test_ble_connection.py -v

# Or exclude integration tests
python -m pytest tests/ -v -m "not integration"
```

---

## Troubleshooting Tests

### BLE Adapter Not Found
**Problem:** Integration tests skip with "BLE adapter not available"

**Solutions:**
1. Ensure adapter is powered on (connected to 12V)
2. Check LED is blinking (pairing mode)
3. Verify address is correct:
   ```bash
   python examples/ble_example.py
   ```
4. Try manual scan:
   ```bash
   bluetoothctl scan on
   ```

### Connection Timeout
**Problem:** Tests fail with timeout errors

**Solutions:**
1. Move closer to BLE adapter
2. Increase `CONNECTION_TIMEOUT` in test file
3. Ensure adapter is not connected to another device
4. Restart adapter (unplug/replug power)

### Import Errors
**Problem:** `ModuleNotFoundError: No module named 'bleak'`

**Solution:**
```bash
pip install bleak
```

---

## Comparison with Bluetooth RFCOMM Tests

| Feature | BLE Tests | RFCOMM Tests |
|---------|-----------|--------------|
| Unit Tests | 22 tests | - |
| Integration Tests | 8 tests | 6 tests |
| Hardware Required | BLE adapter | Classic BT adapter |
| Connection Method | GATT/Characteristics | RFCOMM/Serial Port |
| Typical Runtime | ~74s | ~60s |
| Device Discovery | ✅ Included | ⚠️ Limited |
| Reconnection Tests | ✅ Yes | ✅ Yes |

---

## Future Enhancements

- [ ] Add stress tests (many rapid connections)
- [ ] Test MTU negotiation
- [ ] Test connection parameter updates
- [ ] Mock BLE scanner for discovery tests
- [ ] Performance benchmarks (latency, throughput)
- [ ] Test with multiple BLE adapters
- [ ] Test connection while already connected to phone

---

## Contributing

When adding new BLE functionality:

1. Add unit tests to `test_ble_connection.py`
2. Add integration tests to `test_ble_real.py` if hardware interaction needed
3. Run full test suite before committing
4. Update this README with new test descriptions
