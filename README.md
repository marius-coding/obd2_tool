
# obd2_tool

**A Python toolkit for OBD-II diagnostics, with advanced support for ELM327 adapters and electric vehicles (Kia Niro EV).**

## Overview

`obd2_tool` is a modular Python library for automotive diagnostics using OBD-II protocols. It provides robust drivers for ELM327-based adapters, ISO-TP protocol handling, and high-level interfaces for vehicle-specific diagnostics (e.g., Kia Niro EV).

- **ELM327 Driver:** Communicate with OBD-II adapters via serial.
- **ISO-TP Protocol:** Parse and assemble multi-frame CAN messages.
- **Kia Niro EV Support:** Read battery, cell voltages, and other EV-specific data.
- **Mock Serial:** Simulate ELM327 responses for testing and development.

## Features

- Automatic ELM327 port detection and error handling
- ISO-TP (ISO 15765-2) multi-frame message parsing
- Unified Diagnostic Services (UDS) support
- High-level API for Kia Niro EV diagnostics
- Comprehensive test suite with mock serial support
- Extensible architecture for new vehicles and protocols

## Installation

```bash
git clone https://github.com/marius-coding/obd2_tool.git
cd obd2_tool
pip install -r requirements.txt
```

> **Note:** Requires Python 3.10+ and `pyserial`. For development, see `STYLE_GUIDE.md`.

## Usage

### Example: Kia Niro EV Diagnostics

```bash
python examples/kia_niro_ev_demo.py --mock
```

- By default, runs with simulated data (mock serial).
- Remove `--mock` to connect to a real ELM327 device.

### Library Usage

```python
from driver.elm327 import ELM327
from driver.kia_niro_ev import KiaNiroEV

elm = ELM327()  # auto-detects port
niro = KiaNiroEV(elm)
soc = niro.get_soc()
print(f"State of Charge: {soc}%")
```

## Documentation

- [ELM327 Response Formats](docs/ELM327_RESPONSE_FORMATS.md)
- [ISO-TP Refactoring](docs/ISOTP_REFACTORING.md)
- [Kia Niro EV Implementation](docs/KIA_NIRO_EV_IMPLEMENTATION.md)
- [Style Guide](STYLE_GUIDE.md)

## Testing

Run all tests:

```bash
python -m unittest discover tests
```

## Contributing

- Follow the [Style Guide](STYLE_GUIDE.md).
- Write docstrings and type hints for all public APIs.
- Ensure all code passes linting and tests before submitting a PR.

## License

BSD 3-Clause License. See `LICENSE` for details.
