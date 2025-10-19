# Kia Niro EV Implementation

## Overview

This document describes the implementation of the Kia Niro EV diagnostic interface based on the OBD-PIDs specifications from the [JejuSoul/OBD-PIDs-for-HKMC-EVs](https://github.com/JejuSoul/OBD-PIDs-for-HKMC-EVs) repository.

## Architecture

The `KiaNiroEV` class provides a high-level interface to read diagnostic data from a Kia Niro EV using UDS (Unified Diagnostic Services) commands over ISO-TP protocol.

### Components

- **ELM327**: Low-level driver for ELM327-based OBD-II adapters
- **KiaNiroEV**: High-level interface for Kia Niro EV specific diagnostics
- **ISO-TP**: Protocol handler for multi-frame messages

## CAN Configuration

- **BMS Request ID**: 0x7E4 (2020 in decimal)
- **BMS Response ID**: 0x7EC (2028 in decimal)

## Supported PIDs

### PID 0x0101 - Main BMS Data

This PID provides the primary battery management system data including:

- **State of Charge (SOC)**: Battery percentage
- **Battery Voltage**: Main DC voltage
- **Battery Current**: Charge/discharge current
- **Cell Voltages**: Min/max cell voltages and their locations
- **Battery Temperatures**: Multiple temperature sensors

### PID 0x0102-0x0104 - Cell Voltages

These PIDs provide individual cell voltage data for all 98 battery cells:

- **0x0102**: Cells 1-32
- **0x0103**: Cells 33-64
- **0x0104**: Cells 65-96

### PID 0x0105 - Extended Data

Includes:

- Cells 97-98 voltages
- State of Health (SOH)
- Additional diagnostic data

## Data Parsing

### CSV Notation to Byte Index

The CSV files use a letter notation (a, b, c, ..., z, aa, ab, ...) to represent byte positions in the response payload. This maps to 0-indexed byte positions:

- `a` → byte 0
- `b` → byte 1
- `e` → byte 4
- `z` → byte 25
- `aa` → byte 26

### Example: State of Charge

**CSV Entry**: `000_State of Charge BMS,SOC BMS,0x220101,e/2,0,100,%,7E4`

**Interpretation**:
- PID: 0x220101 (service 0x22, data ID 0x0101)
- Formula: `e/2` (byte at position 4, divided by 2)
- Range: 0-100%
- CAN ID: 0x7E4

**Real Trace Example**:
```
Send: 220101
Response: 
7EC 10 3E 62 01 01 EF FB E7 ED 69 00 00 00 00 00
7EC 21 00 00 0E 26 0D 0C 0D 0D 0D 00 00 00 34 BC
7EC 22 18 BC 56 00 00 7C 00 02 DE 80 00 02 C9 55
7EC 23 00 01 19 AF 00 01 07 C3 00 EC 65 6F 00 00
7EC 24 03 00 00 00 00 0B B8
```

**ISO-TP Reassembly**:
1. First frame (10 3E): Message length = 0x3E (62 bytes)
2. Data starts after header: `62 01 01 EF FB E7 ED 69 ...`
   - Service ID: 0x62 (positive response to 0x22)
   - Data ID: 0x01 01
   - Payload: `EF FB E7 ED 69 ...`
3. SOC byte (position 4 in payload): 0x69 = 105 decimal
4. SOC = 105 / 2 = **52.5%**

## API Reference

### Initialization

```python
from driver.elm327 import ELM327
from driver.kia_niro_ev import KiaNiroEV

# Connect to ELM327
elm = ELM327()  # Auto-detects port

# Create Kia Niro EV interface
kia = KiaNiroEV(elm)
```

### Available Methods

#### `get_soc() -> float`

Returns the State of Charge as a percentage (0-100%).

```python
soc = kia.get_soc()
print(f"Battery: {soc:.1f}%")
```

#### `get_cell_voltage(cell: int) -> float`

Returns voltage of a specific battery cell (1-98) in volts.

```python
voltage = kia.get_cell_voltage(1)
print(f"Cell 1: {voltage:.3f}V")
```

#### `get_battery_voltage() -> float`

Returns the main battery DC voltage in volts.

```python
voltage = kia.get_battery_voltage()
print(f"Battery: {voltage:.1f}V")
```

#### `get_battery_current() -> float`

Returns battery current in amperes. Negative values indicate charging, positive values indicate discharging.

```python
current = kia.get_battery_current()
print(f"Current: {current:.1f}A")
```

#### `get_max_cell_voltage() -> tuple[float, int]`

Returns the maximum cell voltage and the cell number.

```python
voltage, cell_no = kia.get_max_cell_voltage()
print(f"Max: {voltage:.3f}V at cell {cell_no}")
```

#### `get_min_cell_voltage() -> tuple[float, int]`

Returns the minimum cell voltage and the cell number.

```python
voltage, cell_no = kia.get_min_cell_voltage()
print(f"Min: {voltage:.3f}V at cell {cell_no}")
```

#### `get_soh() -> float`

Returns State of Health as a percentage.

```python
soh = kia.get_soh()
print(f"SOH: {soh:.1f}%")
```

#### `get_battery_temperatures() -> dict[str, float]`

Returns dictionary of battery temperatures in Celsius:
- `max`: Maximum temperature
- `min`: Minimum temperature  
- `inlet`: Inlet temperature
- `module_01` through `module_04`: Individual module temperatures

```python
temps = kia.get_battery_temperatures()
print(f"Max temp: {temps['max']}°C")
print(f"Min temp: {temps['min']}°C")
```

## Testing

The implementation includes comprehensive unit tests using mock serial data based on real trace captures.

### Run Tests

```bash
python -m pytest tests/test_kia_niro_ev.py -v
```

### Test Coverage

- ✅ SOC reading (validated with real trace: 52.5%)
- ✅ Battery voltage reading
- ✅ Max cell voltage reading
- ✅ Temperature readings

## References

- [OBD-PIDs-for-HKMC-EVs Repository](https://github.com/JejuSoul/OBD-PIDs-for-HKMC-EVs)
- [ISO 15765-2 (ISO-TP)](https://en.wikipedia.org/wiki/ISO_15765-2)
- [UDS (ISO 14229)](https://en.wikipedia.org/wiki/Unified_Diagnostic_Services)

## Notes

- The Kia Niro EV has 98 battery cells arranged in modules
- All voltage measurements use the formula `raw_value / 50.0`
- Temperature values are signed bytes (can be negative for cold climates)
- The BMS updates data in real-time while the vehicle is powered on
