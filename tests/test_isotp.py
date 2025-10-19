"""
Unit tests for ISO-TP protocol handler.

Tests ISO-TP frame parsing and message assembly.
"""

import unittest
from driver.isotp import IsoTpFrame, IsoTpMessage, parse_isotp_frames


class TestIsoTpFrame(unittest.TestCase):
    """
    Test suite for ISO-TP frame parsing.

    Tests different frame types according to ISO 15765-2.
    """

    def test_single_frame(self) -> None:
        """
        Test parsing of single-frame ISO-TP message.

        Single frame format: 0x0L DD DD DD...
        """
        # Single frame with 5 bytes of data
        frame_data = bytearray.fromhex('05 62 01 02 FF FF')
        frame = IsoTpFrame(frame_data)
        
        self.assertEqual(frame.frame_type, IsoTpFrame.SINGLE_FRAME)
        self.assertEqual(frame.length, 5)
        self.assertEqual(frame.data, bytearray.fromhex('62 01 02 FF FF'))

    def test_first_frame(self) -> None:
        """
        Test parsing of first frame in multi-frame ISO-TP message.

        First frame format: 0x1L LL DD DD DD...
        """
        # First frame indicating 39 bytes total (0x27)
        frame_data = bytearray.fromhex('10 27 62 01 02 FF FF')
        frame = IsoTpFrame(frame_data)
        
        self.assertEqual(frame.frame_type, IsoTpFrame.FIRST_FRAME)
        self.assertEqual(frame.length, 0x27)
        self.assertEqual(frame.data, bytearray.fromhex('62 01 02 FF FF'))

    def test_consecutive_frame(self) -> None:
        """
        Test parsing of consecutive frame in multi-frame ISO-TP message.

        Consecutive frame format: 0x2N DD DD DD...
        """
        # Consecutive frame with sequence 1
        frame_data = bytearray.fromhex('21 FF BC BC BC BC BC')
        frame = IsoTpFrame(frame_data)
        
        self.assertEqual(frame.frame_type, IsoTpFrame.CONSECUTIVE_FRAME)
        self.assertEqual(frame.sequence_number, 1)
        self.assertEqual(frame.data, bytearray.fromhex('FF BC BC BC BC BC'))

    def test_empty_frame(self) -> None:
        """
        Test that empty frame data raises ValueError.
        """
        with self.assertRaises(ValueError):
            IsoTpFrame(bytearray())


class TestIsoTpMessage(unittest.TestCase):
    """
    Test suite for ISO-TP message assembly.

    Tests assembling frames into complete messages.
    """

    def test_single_frame_message(self) -> None:
        """
        Test assembling a single-frame message.
        """
        message = IsoTpMessage()
        frame = IsoTpFrame(bytearray.fromhex('05 62 01 02 FF FF'))
        message.add_frame(frame)
        
        self.assertTrue(message.is_complete)
        self.assertEqual(message.get_payload(), bytearray.fromhex('62 01 02 FF FF'))

    def test_multi_frame_message(self) -> None:
        """
        Test assembling a multi-frame message.

        Uses frames from the recorded trace: 0x22 0x01 0x02 response.
        """
        message = IsoTpMessage()
        
        # First frame: 0x10 0x27 = length 39, followed by 5 bytes of data
        first_frame = IsoTpFrame(bytearray.fromhex('10 27 62 01 02 FF FF'))
        message.add_frame(first_frame)
        self.assertFalse(message.is_complete)
        self.assertEqual(len(message.payload), 5)
        
        # Consecutive frames: 6 bytes each
        message.add_frame(IsoTpFrame(bytearray.fromhex('21 FF BC BC BC BC BC')))
        self.assertFalse(message.is_complete)
        self.assertEqual(len(message.payload), 11)
        
        message.add_frame(IsoTpFrame(bytearray.fromhex('22 BC BC BC BC BC BC')))
        self.assertFalse(message.is_complete)
        self.assertEqual(len(message.payload), 17)
        
        message.add_frame(IsoTpFrame(bytearray.fromhex('23 BC BC BC BC BC BC')))
        self.assertFalse(message.is_complete)
        self.assertEqual(len(message.payload), 23)
        
        message.add_frame(IsoTpFrame(bytearray.fromhex('24 BC BC BC BC BC BC')))
        self.assertFalse(message.is_complete)
        self.assertEqual(len(message.payload), 29)
        
        message.add_frame(IsoTpFrame(bytearray.fromhex('25 BC BC BC BC BC BC')))
        self.assertFalse(message.is_complete)
        self.assertEqual(len(message.payload), 35)
        
        # One more frame to complete
        message.add_frame(IsoTpFrame(bytearray.fromhex('26 BC BC BC BC AA AA')))
        self.assertTrue(message.is_complete)
        
        payload = message.get_payload()
        self.assertEqual(len(payload), 0x27)  # 39 bytes

    def test_sequence_validation(self) -> None:
        """
        Test that incorrect sequence numbers are detected.
        """
        message = IsoTpMessage()
        
        # First frame
        message.add_frame(IsoTpFrame(bytearray.fromhex('10 10 62 01 02 FF FF')))
        
        # Skip sequence 1, try sequence 2 - should fail
        with self.assertRaises(ValueError):
            message.add_frame(IsoTpFrame(bytearray.fromhex('22 BC BC BC BC BC BC')))

    def test_consecutive_without_first(self) -> None:
        """
        Test that consecutive frame without first frame raises error.
        """
        message = IsoTpMessage()
        
        with self.assertRaises(ValueError):
            message.add_frame(IsoTpFrame(bytearray.fromhex('21 BC BC BC BC BC BC')))

    def test_payload_before_complete(self) -> None:
        """
        Test that getting payload before message is complete raises error.
        """
        message = IsoTpMessage()
        message.add_frame(IsoTpFrame(bytearray.fromhex('10 10 62 01 02 FF FF')))
        
        with self.assertRaises(ValueError):
            message.get_payload()


class TestParseIsoTpFrames(unittest.TestCase):
    """
    Test suite for parse_isotp_frames convenience function.

    Tests the high-level API for ISO-TP parsing.
    """

    def test_parse_single_frame(self) -> None:
        """
        Test parsing single frame using convenience function.
        """
        frames = ['0562010205FF']
        payload = parse_isotp_frames(frames)
        
        self.assertEqual(payload, bytearray.fromhex('62 01 02 05 FF'))

    def test_parse_multi_frame_from_trace(self) -> None:
        """
        Test parsing multi-frame message from recorded trace.

        Uses actual frame data from trace for 0x22 0x01 0x02 response.
        """
        frames = [
            '1027620102FFFFFF',  # First frame
            '21FFBCBCBCBCBCBC',  # Consecutive frame 1
            '22BCBCBCBCBCBCBC',  # Consecutive frame 2
            '23BCBCBCBCBCBCBC',  # Consecutive frame 3
            '24BCBCBCBCBCBCBC',  # Consecutive frame 4
            '25BCBCBCBCBCAAAA',  # Consecutive frame 5 (partial)
        ]
        
        payload = parse_isotp_frames(frames)
        
        # Verify length is 0x27 (39 bytes)
        self.assertEqual(len(payload), 0x27)
        
        # Verify first bytes are the response code and data ID
        self.assertEqual(payload[0], 0x62)
        self.assertEqual(payload[1], 0x01)
        self.assertEqual(payload[2], 0x02)


if __name__ == '__main__':
    unittest.main()
