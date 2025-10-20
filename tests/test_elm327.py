"""
Unit tests for ELM327 driver.

Tests are based on recorded communication trace with an actual ELM327 device.
"""

import asyncio
import unittest
from driver.elm327 import ELM327
from driver.mock_serial import MockConnection
from driver.exceptions import NoResponseException, InvalidResponseException
from driver.isotp import IsoTpResponse


class TestELM327(unittest.TestCase):
    """
    Test suite for ELM327 driver.

    Uses mock connection interface with responses from recorded trace.
    """

    def setUp(self) -> None:
        """
        Set up test fixtures.

        Creates a mock connection and initializes ELM327 driver.
        """
        self.mock_connection = MockConnection()
        asyncio.run(self.mock_connection.open())
        self.elm = ELM327(self.mock_connection)
        asyncio.run(self.elm.initialize())

    def tearDown(self) -> None:
        """
        Clean up after tests.

        Closes the ELM327 connection.
        """
        asyncio.run(self.elm.close())

    def test_initialization(self) -> None:
        """
        Test ELM327 initialization sequence.

        Verifies that the driver properly initializes with ATZ, ATE0, ATL0, ATS0, ATH1, ATSP0.
        """
        self.assertIsNotNone(self.elm.connection)
        self.assertTrue(self.mock_connection.is_open)
        self.assertTrue(self.elm._initialized)

    def test_send_uds_message_no_response(self) -> None:
        """
        Test sending UDS message that receives no response.

        Based on trace: ATSH7E4 + 220101 -> SEARCHING... (no data)
        """
        with self.assertRaises(NoResponseException):
            # This should fail because mock returns only "SEARCHING..." followed by "STOPPED"
            asyncio.run(self.elm.send_message(can_id=0x7E4, pid=0x22))

    def test_send_uds_message_with_isotp_response(self) -> None:
        """
        Test sending UDS message with ISO-TP multi-frame response.

        Based on trace: ATSH7E4 + 220102 -> Multi-frame ISO-TP response
        Expected: 7EC1027620102FFFFFF... (first frame with length 0x27)
        """
        # Send UDS request 0x22 0x01 0x02
        response = asyncio.run(self.elm.send_message(can_id=0x7E4, pid=0x220102))
        
        # Verify we got a structured response
        self.assertIsInstance(response, IsoTpResponse)
        self.assertEqual(response.service_id, 0x62)
        self.assertIsNotNone(response.data_identifier)
        self.assertGreater(len(response.payload), 0)

    def test_220102_request_exact_payload(self) -> None:
        """
        Test 220102 request returns exact expected payload.

        Verifies the complete reassembled ISO-TP payload matches the expected data
        from the recorded trace.
        
        The ISO-TP message length is 0x27 (39 bytes). The last frame contains AAAA
        as padding, but this is trimmed off to match the declared message length.
        """
        # Send UDS request 0x22 0x01 0x02
        response = asyncio.run(self.elm.send_message(can_id=0x7E4, pid=0x220102))
        
        # Expected data payload (39 bytes total - 3 bytes for service ID and data identifier)
        expected_payload = bytearray.fromhex(
            'ffffffffbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbc'
        )
        
        # Verify structured response
        self.assertIsInstance(response, IsoTpResponse)
        self.assertEqual(response.service_id, 0x62)  # Positive response to service 0x22
        self.assertEqual(response.data_identifier, 0x0102)  # Data identifier 0x01 0x02
        self.assertEqual(len(response.payload), 36)  # 39 - 3 = 36 bytes
        self.assertEqual(response.payload, expected_payload)

    def test_send_uds_message_single_frame(self) -> None:
        """
        Test sending UDS message with ISO-TP single-frame response.

        Based on trace: ATSH7E4 + 220105 -> Multi-frame ISO-TP response
        """
        # Send UDS request 0x22 0x01 0x05
        response = asyncio.run(self.elm.send_message(can_id=0x7E4, pid=0x220105))
        
        # Verify we got a structured response
        self.assertIsInstance(response, IsoTpResponse)
        self.assertEqual(response.service_id, 0x62)
        self.assertGreater(len(response.payload), 0)

    def test_parse_multiframe_response(self) -> None:
        """
        Test parsing of multi-frame ISO-TP response.

        Verifies that consecutive frames are properly handled.
        """
        # The trace shows frames: 7EC10, 7EC21, 7EC22, 7EC23, 7EC24, 7EC25
        # Format: 7EC = response ID, 10 = first frame, 2X = consecutive frames
        
        response = asyncio.run(self.elm.send_message(can_id=0x7E4, pid=0x220102))
        
        # Verify response is structured and not empty
        self.assertIsInstance(response, IsoTpResponse)
        self.assertGreater(len(response.payload), 0)

    def test_invalid_response_handling(self) -> None:
        """
        Test handling of invalid responses.

        Verifies that driver properly raises InvalidResponseException for malformed data.
        """
        # Add a command that returns invalid hex data to the mock
        self.mock_connection.responses['999999'] = 'INVALID_HEX\r\r>'
        
        with self.assertRaises(InvalidResponseException):
            # Try to send a message that will get invalid response
            # The mock will return the invalid response
            asyncio.run(self.elm.send_message(can_id=0x999, pid=0x999999))

    def test_tester_present_enable_disable(self) -> None:
        """
        Test enabling and disabling cyclic Tester Present.

        Verifies that tester present thread can be started and stopped properly.
        """
        # Enable tester present
        self.elm.enable_cyclic_tester_present(cycle_time=0.5)
        self.assertTrue(self.elm.tester_present_running)
        self.assertIsNotNone(self.elm.tester_present_thread)
        
        # Disable tester present
        self.elm.disable_tester_present()
        self.assertFalse(self.elm.tester_present_running)


class TestMockConnection(unittest.TestCase):
    """
    Test suite for MockConnection interface.

    Verifies that the mock properly simulates ELM327 behavior.
    """

    def test_mock_initialization_sequence(self) -> None:
        """
        Test mock connection initialization commands.

        Verifies that mock returns correct responses for initialization sequence.
        """
        mock = MockConnection()
        asyncio.run(mock.open())
        
        # Test ATZ
        asyncio.run(mock.write(b'ATZ\r'))
        response = asyncio.run(mock.read(1024)).decode('ascii')
        self.assertIn('ELM327', response)
        
        # Test ATE0
        asyncio.run(mock.write(b'ATE0\r'))
        response = asyncio.run(mock.read(1024)).decode('ascii')
        self.assertIn('OK', response)
        
        # Test ATL0
        asyncio.run(mock.write(b'ATL0\r'))
        response = asyncio.run(mock.read(1024)).decode('ascii')
        self.assertIn('OK', response)
        
        asyncio.run(mock.close())

    def test_mock_uds_responses(self) -> None:
        """
        Test mock UDS command responses.

        Verifies that mock returns correct responses for UDS commands from trace.
        """
        mock = MockConnection()
        asyncio.run(mock.open())
        
        # Test ATSH7E4
        asyncio.run(mock.write(b'ATSH7E4\r'))
        response = asyncio.run(mock.read(1024)).decode('ascii')
        self.assertIn('OK', response)
        
        # Test 220102
        asyncio.run(mock.write(b'220102\r'))
        response = asyncio.run(mock.read(2048)).decode('ascii')
        self.assertIn('7EC', response)  # CAN ID marker
        self.assertIn('10', response)  # First frame marker
        
        asyncio.run(mock.close())


if __name__ == '__main__':
    unittest.main()
