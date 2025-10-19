# ELM327 Response Format Handling

## Overview

The ELM327 driver has been updated to handle multiple response formats that can be returned by real ELM327 devices.

## Supported Response Formats

### 1. Response with Spaces Between Bytes (Most Common)

This is the format typically returned by real ELM327 devices:

```
7EC 10 3E 62 01 01 EF FB E7 
7EC 21 ED 69 00 00 00 00 00 
7EC 22 00 00 0E 26 0D 0C 0D 
...
```

Each line represents one CAN frame:
- `7EC` = CAN ID (3 hex digits)
- Following bytes are space-separated data

### 2. Response without Spaces (Compact Format)

Some devices or configurations may return compact format:

```
7EC103E620101EFFBE7ED69
7EC2100000E260D0C0D0D0D
7EC2218BC5600007C0002DE
...
```

Same structure but without spaces between bytes.

### 3. Mixed Format

The parser handles responses that may contain:
- Informational messages: `SEARCHING...`, `BUSINIT...`, `OK`
- Error messages: `NO DATA`, `ERROR`, `STOPPED`, `UNABLE TO CONNECT`, `CAN ERROR`, `BUFFER FULL`
- Multiple line break formats: `\r`, `\n`, `\r\r`

## Parser Behavior

The `_parse_response()` method in `elm327.py`:

1. **Removes informational messages** that aren't actual data
2. **Checks for error conditions** and raises exceptions
3. **Processes line-by-line** to avoid CAN ID collision
4. **Normalizes spacing** within each line
5. **Extracts CAN frame data** after validating CAN ID
6. **Assembles ISO-TP frames** into complete messages

### Key Algorithm

```python
for line in lines:
    line_no_spaces = line.replace(' ', '')
    can_id = line_no_spaces[:3]  # Extract CAN ID
    if is_valid_hex(can_id):
        frame_data = line_no_spaces[3:]  # Data after CAN ID
        frame_data_list.append(frame_data)
```

This approach ensures:
- ✅ Spaces within a line don't cause issues
- ✅ Line breaks properly separate CAN frames
- ✅ Both formats work identically

## Error Handling

The driver recognizes these ELM327 status/error messages:

| Message | Meaning |
|---------|---------|
| `NO DATA` | ECU not responding |
| `ERROR` | General error |
| `?` | Unknown command |
| `STOPPED` | Data stream stopped |
| `UNABLE TO CONNECT` | Cannot connect to ECU |
| `BUS INIT` | Bus initialization message |
| `CAN ERROR` | CAN bus error |
| `BUFFER FULL` | Internal buffer overflow |
| `<DATA ERROR` | Data transmission error |

When detected, these raise a `NoResponseException` with the full message.

## Testing

The implementation has been validated with:

1. **Real Kia Niro EV trace data** (with spaces)
2. **Synthetic test data** (without spaces) 
3. **Mixed format responses**

All 14 unit tests pass, covering:
- Single-frame ISO-TP responses
- Multi-frame ISO-TP responses
- Error condition handling
- Both response formats

## Example Trace

Real trace from Kia Niro EV showing SOC = 52.5%:

```
Send: 220101
Response:
7EC 10 3E 62 01 01 EF FB E7 
7EC 21 ED 69 00 00 00 00 00 
7EC 22 00 00 0E 26 0D 0C 0D 
7EC 23 0D 0D 00 00 00 34 BC 
7EC 24 18 BC 56 00 00 7C 00 
7EC 25 02 DE 80 00 02 C9 55 
7EC 26 00 01 19 AF 00 01 07 
7EC 27 C3 00 EC 65 6F 00 00 
7EC 28 03 00 00 00 00 0B B8 
```

Parsed result:
- Service: 0x62 (positive response to 0x22)
- Data ID: 0x0101
- Payload byte 4: 0x69 = 105
- SOC = 105 / 2 = **52.5%** ✓

## Implementation Files

- **Driver**: `driver/elm327.py` - `_parse_response()` method
- **Tests**: `tests/test_elm327.py`, `tests/test_kia_niro_ev.py`
- **Mock Data**: `driver/mock_serial.py`
