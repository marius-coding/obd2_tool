"""
ISO-TP (ISO 15765-2) protocol handler.

This module provides functionality for parsing and assembling ISO-TP messages
used in automotive diagnostic protocols.
"""

from dataclasses import dataclass


@dataclass
class IsoTpResponse:
    """
    Represents a parsed ISO-TP response message.

    This dataclass encapsulates a complete ISO-TP diagnostic response with
    separated fields for easier processing.

    Attributes:
        service_id (int): Response service identifier (e.g., 0x62 for positive response to 0x22).
        data_identifier (int | None): Data identifier for services that use it (e.g., 0x22 ReadDataByIdentifier).
        payload (bytearray): The actual data payload (excluding service ID and data identifier).
    """
    service_id: int
    data_identifier: int | None
    payload: bytearray

    def __str__(self) -> str:
        """
        Return human-readable string representation.

        Returns:
            str: Formatted string with service ID, data identifier, and payload length.
        """
        if self.data_identifier is not None:
            return f"IsoTpResponse(service_id=0x{self.service_id:02X}, data_id=0x{self.data_identifier:04X}, payload_len={len(self.payload)})"
        return f"IsoTpResponse(service_id=0x{self.service_id:02X}, payload_len={len(self.payload)})"


class IsoTpFrame:
    """
    Represents a single ISO-TP frame.

    ISO-TP frames can be single frames, first frames, consecutive frames, or flow control frames.

    Attributes:
        frame_type (int): Type of frame (0=single, 1=first, 2=consecutive, 3=flow control).
        data (bytearray): Frame data payload.
        sequence_number (int | None): Sequence number for consecutive frames.
        length (int | None): Total message length for first frames.
    """

    SINGLE_FRAME = 0
    FIRST_FRAME = 1
    CONSECUTIVE_FRAME = 2
    FLOW_CONTROL_FRAME = 3

    def __init__(self, frame_bytes: bytearray) -> None:
        """
        Initialize ISO-TP frame from raw bytes.

        Args:
            frame_bytes (bytearray): Raw frame data including PCI byte(s).

        Raises:
            ValueError: If frame data is invalid or too short.
        """
        if len(frame_bytes) == 0:
            raise ValueError("Frame data cannot be empty")

        # Get PCI (Protocol Control Info) - first nibble
        self.frame_type = (frame_bytes[0] & 0xF0) >> 4
        self.data = bytearray()
        self.sequence_number: int | None = None
        self.length: int | None = None

        if self.frame_type == self.SINGLE_FRAME:
            # Single frame: 0x0L DD DD DD...
            # L = length (0-7)
            self.length = frame_bytes[0] & 0x0F
            self.data = frame_bytes[1:1 + self.length]

        elif self.frame_type == self.FIRST_FRAME:
            # First frame: 0x1L LL DD DD DD...
            # L LL = length (12 bits)
            self.length = ((frame_bytes[0] & 0x0F) << 8) | frame_bytes[1]
            self.data = frame_bytes[2:]

        elif self.frame_type == self.CONSECUTIVE_FRAME:
            # Consecutive frame: 0x2N DD DD DD...
            # N = sequence number (0-15)
            self.sequence_number = frame_bytes[0] & 0x0F
            self.data = frame_bytes[1:]

        elif self.frame_type == self.FLOW_CONTROL_FRAME:
            # Flow control frame: 0x3F BS ST
            # Not typically needed for receive-only operations
            pass


class IsoTpMessage:
    """
    Assembles ISO-TP frames into complete messages.

    Handles single-frame and multi-frame ISO-TP messages according to ISO 15765-2.

    Attributes:
        payload (bytearray): Complete assembled message payload.
        expected_length (int | None): Expected total message length.
        is_complete (bool): Whether the message assembly is complete.
    """

    def __init__(self) -> None:
        """
        Initialize empty ISO-TP message.
        """
        self.payload = bytearray()
        self.expected_length: int | None = None
        self.is_complete = False
        self._next_sequence = 1

    def add_frame(self, frame: IsoTpFrame) -> None:
        """
        Add a frame to the message assembly.

        Frames must be added in the correct order (first frame, then consecutive frames).

        Args:
            frame (IsoTpFrame): Frame to add to the message.

        Raises:
            ValueError: If frame is added in wrong order or sequence is invalid.
        """
        if self.is_complete:
            raise ValueError("Message is already complete")

        if frame.frame_type == IsoTpFrame.SINGLE_FRAME:
            # Single frame contains complete message
            self.payload = frame.data
            self.expected_length = frame.length
            self.is_complete = True

        elif frame.frame_type == IsoTpFrame.FIRST_FRAME:
            # First frame starts multi-frame message
            if len(self.payload) > 0:
                raise ValueError("First frame received but message already started")
            self.payload.extend(frame.data)
            self.expected_length = frame.length
            self._next_sequence = 1

            # Check if we have all data already
            if self.expected_length is not None and len(self.payload) >= self.expected_length:
                self.is_complete = True

        elif frame.frame_type == IsoTpFrame.CONSECUTIVE_FRAME:
            # Consecutive frame adds to existing message
            if self.expected_length is None:
                raise ValueError("Consecutive frame received without first frame")

            # Verify sequence number
            if frame.sequence_number != self._next_sequence:
                raise ValueError(f"Expected sequence {self._next_sequence}, got {frame.sequence_number}")

            self.payload.extend(frame.data)
            self._next_sequence = (self._next_sequence + 1) % 16

            # Check if message is complete
            if len(self.payload) >= self.expected_length:
                # Trim to expected length
                self.payload = self.payload[:self.expected_length]
                self.is_complete = True

    def get_payload(self) -> bytearray:
        """
        Get the complete message payload.

        Returns:
            bytearray: Complete assembled payload.

        Raises:
            ValueError: If message is not yet complete.
        """
        if not self.is_complete:
            raise ValueError("Message is not complete yet")
        return self.payload


def parse_isotp_frames(frame_data_list: list[str]) -> bytearray:
    """
    Parse a list of ISO-TP frame data strings and assemble into complete message.

    This is a convenience function that handles the complete ISO-TP assembly process.

    Args:
        frame_data_list (list[str]): List of hex strings, each representing one frame's data.

    Returns:
        bytearray: Complete assembled ISO-TP message payload.

    Raises:
        ValueError: If frames are invalid or cannot be assembled.
    """
    message = IsoTpMessage()

    for frame_data in frame_data_list:
        frame_bytes = bytearray.fromhex(frame_data)
        frame = IsoTpFrame(frame_bytes)
        message.add_frame(frame)

    return message.get_payload()


def parse_uds_response(payload: bytearray) -> IsoTpResponse:
    """
    Parse a UDS (Unified Diagnostic Services) response payload.

    Extracts the service ID, optional data identifier, and payload from the raw data.

    Args:
        payload (bytearray): Complete ISO-TP message payload.

    Returns:
        IsoTpResponse: Parsed response with separated fields.

    Raises:
        ValueError: If payload is too short or invalid.
    """
    if len(payload) < 1:
        raise ValueError("Payload too short for UDS response")

    service_id = payload[0]
    
    # Services that include a 2-byte data identifier (e.g., 0x22/0x62 ReadDataByIdentifier)
    services_with_data_id = [0x22, 0x62, 0x2E, 0x6E, 0x2F, 0x6F]
    
    if service_id in services_with_data_id:
        if len(payload) < 3:
            raise ValueError(f"Payload too short for service 0x{service_id:02X} with data identifier")
        
        # Data identifier is 2 bytes (big-endian)
        data_identifier = (payload[1] << 8) | payload[2]
        data_payload = bytearray(payload[3:])
        
        return IsoTpResponse(
            service_id=service_id,
            data_identifier=data_identifier,
            payload=data_payload
        )
    else:
        # No data identifier for this service
        data_payload = bytearray(payload[1:])
        
        return IsoTpResponse(
            service_id=service_id,
            data_identifier=None,
            payload=data_payload
        )
