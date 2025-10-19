"""
Custom exceptions for ELM327 driver.

This module defines all custom exception classes used by the ELM327 driver
for better error handling and differentiation.
"""


class ELM327Exception(Exception):
    """
    Base exception for all ELM327-related errors.

    This is the parent class for all custom exceptions raised by the ELM327 driver.
    """
    pass


class DeviceNotFoundException(ELM327Exception):
    """
    Exception raised when no ELM327 device is found.

    Raised during automatic port detection when no ELM327 adapter can be found
    on any available serial port.
    """
    pass


class ConnectionException(ELM327Exception):
    """
    Exception raised when connection to ELM327 device fails.

    Raised when the serial connection cannot be established or the device
    fails to initialize properly.
    """
    pass


class NoResponseException(ELM327Exception):
    """
    Exception raised when ECU or ELM327 does not respond.

    Raised when a command is sent but no valid response is received, typically
    indicating the ECU is not responding or the ELM327 encountered an error.
    """
    pass


class InvalidResponseException(ELM327Exception):
    """
    Exception raised when response format is invalid.

    Raised when the ELM327 returns data that cannot be parsed or is in an
    unexpected format.
    """
    pass


class NotConnectedException(ELM327Exception):
    """
    Exception raised when attempting operations without an active connection.

    Raised when trying to send commands or messages while no serial connection
    is established to the ELM327 device.
    """
    pass
