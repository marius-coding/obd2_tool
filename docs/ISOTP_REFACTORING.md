# ISO-TP Module Refactoring Summary

## Overview
Separated ISO-TP (ISO 15765-2) protocol parsing logic from ELM327 driver into a dedicated, reusable module.

## New Files Created

### `driver/isotp.py`
A standalone ISO-TP protocol handler with three main components:

1. **`IsoTpFrame`** - Represents and parses individual ISO-TP frames
   - Single frames (0x0X)
   - First frames (0x1X)
   - Consecutive frames (0x2X)
   - Flow control frames (0x3X)

2. **`IsoTpMessage`** - Assembles frames into complete messages
   - Handles multi-frame reassembly
   - Validates sequence numbers
   - Tracks completion status
   - Trims payload to expected length

3. **`parse_isotp_frames()`** - Convenience function for one-step parsing

### `tests/test_isotp.py`
Comprehensive test suite with 11 tests:
- Frame parsing tests (4 tests)
- Message assembly tests (5 tests)
- High-level API tests (2 tests)

## Changes to Existing Files

### `driver/elm327.py`
- **Removed**: ~40 lines of ISO-TP parsing logic from `_parse_response()`
- **Added**: Import and usage of `parse_isotp_frames()`
- **Result**: Cleaner, more maintainable code with single responsibility

### `driver/__init__.py`
- Exported ISO-TP classes: `IsoTpFrame`, `IsoTpMessage`, `parse_isotp_frames`

## Benefits

1. **Separation of Concerns**
   - ELM327 driver handles serial communication and ELM327-specific protocol
   - ISO-TP module handles ISO 15765-2 protocol parsing
   - Each module has a single, well-defined responsibility

2. **Reusability**
   - ISO-TP module can be used with other CAN adapters (not just ELM327)
   - Clean API for direct ISO-TP message handling

3. **Testability**
   - ISO-TP logic can be tested independently
   - 11 dedicated tests for ISO-TP functionality
   - Easier to debug and maintain

4. **Maintainability**
   - ISO-TP protocol changes only affect one module
   - Clear boundaries between components
   - Well-documented with comprehensive docstrings

## Test Results
✅ **All 20 tests passing**
- 9 ELM327 driver tests
- 11 ISO-TP module tests

## Usage Example

```python
from driver import IsoTpMessage, IsoTpFrame

# Parse individual frames
frame1 = IsoTpFrame(bytearray.fromhex('10 27 62 01 02 FF FF'))
frame2 = IsoTpFrame(bytearray.fromhex('21 FF BC BC BC BC BC'))

# Assemble message
message = IsoTpMessage()
message.add_frame(frame1)
message.add_frame(frame2)
# ... add more frames ...

payload = message.get_payload()

# Or use convenience function
from driver import parse_isotp_frames

frames = ['1027620102FFFFFF', '21FFBCBCBCBCBCBC', ...]
payload = parse_isotp_frames(frames)
```

## Compliance
Follows project style guide:
- ✅ Strict type hints on all methods
- ✅ Comprehensive docstrings (brief + detailed)
- ✅ PEP 8 compliant (max 110 chars per line)
- ✅ Clear, descriptive naming
- ✅ Proper exception handling
