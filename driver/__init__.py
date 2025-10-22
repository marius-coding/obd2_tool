"""
Driver package for OBD-II adapters.

This package provides drivers for various OBD-II adapter types with support
for multiple connection mechanisms (Serial, Bluetooth, etc.).
"""

from .elm327 import ELM327
from .exceptions import (
    ELM327Exception,
    DeviceNotFoundException,
    InvalidResponseException,
    NoResponseException,
    NotConnectedException,
)
from .isotp import IsoTpFrame, IsoTpMessage, IsoTpResponse, parse_isotp_frames, parse_uds_response
from .connection import Connection, ConnectionException, ConnectionTimeoutError, ConnectionError
from .serial_connection import SerialConnection
from .bluetooth_connection import BluetoothConnection
from .ble_connection import BLEConnection
from .mock_serial import MockConnection

# Note: Avoid importing ConnectionException from .exceptions to prevent name collision
# with ConnectionException from .connection
from .exceptions import ConnectionException as ELM327ConnectionException

__all__ = [
    # ELM327 Driver
    'ELM327',
    
    # Connection Layer
    'Connection',
    'SerialConnection',
    'BluetoothConnection',
    'BLEConnection',
    'MockConnection',
    
    # Connection Exceptions
    'ConnectionException',
    'ConnectionTimeoutError',
    'ConnectionError',
    
    # ELM327 Exceptions
    'ELM327Exception',
    'ELM327ConnectionException',  # Renamed to avoid collision
    'DeviceNotFoundException',
    'InvalidResponseException',
    'NoResponseException',
    'NotConnectedException',
    
    # ISO-TP Protocol
    'IsoTpFrame',
    'IsoTpMessage',
    'IsoTpResponse',
    'parse_isotp_frames',
    'parse_uds_response',
]
