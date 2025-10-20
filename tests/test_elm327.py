"""
Unit tests for ELM327 driver.

Tests are based on recorded communication trace with an actual ELM327 device.
"""

import unittest
from driver.elm327 import ELM327
from driver.mock_serial import MockConnection
from driver.exceptions import NoResponseException, InvalidResponseException
from driver.isotp import IsoTpResponse


class TestELM327(unittest.TestCase):
    """Test suite for ELM327 driver using MockConnection."""

    def setUp(self) -> None:
        self.mock_connection = MockConnection()
        self.mock_connection.open()
        self.elm = ELM327(self.mock_connection)
        self.elm.initialize()

    def tearDown(self) -> None:
        self.elm.close()

    def test_initialization(self) -> None:
        self.assertIsNotNone(self.elm.connection)
        self.assertTrue(self.mock_connection.is_open)
        self.assertTrue(self.elm._initialized)

    def test_send_uds_message_no_response(self) -> None:
        with self.assertRaises(NoResponseException):
            # This should fail because mock returns only "SEARCHING..." followed by "STOPPED"
            self.elm.send_message(can_id=0x7E4, pid=0x22)

    def test_send_uds_message_with_isotp_response(self) -> None:
        # Send UDS request 0x22 0x01 0x02
        response = self.elm.send_message(can_id=0x7E4, pid=0x220102)
        self.assertIsInstance(response, IsoTpResponse)
        self.assertEqual(response.service_id, 0x62)
        self.assertIsNotNone(response.data_identifier)
        self.assertGreater(len(response.payload), 0)

    def test_220102_request_exact_payload(self) -> None:
        response = self.elm.send_message(can_id=0x7E4, pid=0x220102)
        expected_payload = bytearray.fromhex(
            'ffffffffbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbcbc'
        )
        self.assertIsInstance(response, IsoTpResponse)
        self.assertEqual(response.service_id, 0x62)
        self.assertEqual(response.data_identifier, 0x0102)
        self.assertEqual(len(response.payload), 36)
        self.assertEqual(response.payload, expected_payload)

    def test_send_uds_message_single_frame(self) -> None:
        response = self.elm.send_message(can_id=0x7E4, pid=0x220105)
        self.assertIsInstance(response, IsoTpResponse)
        self.assertEqual(response.service_id, 0x62)
        self.assertGreater(len(response.payload), 0)

    def test_parse_multiframe_response(self) -> None:
        response = self.elm.send_message(can_id=0x7E4, pid=0x220102)
        self.assertIsInstance(response, IsoTpResponse)
        self.assertGreater(len(response.payload), 0)

    def test_invalid_response_handling(self) -> None:
        self.mock_connection.responses['999999'] = 'INVALID_HEX\r\r>'
        with self.assertRaises(InvalidResponseException):
            self.elm.send_message(can_id=0x999, pid=0x999999)


class TestMockConnection(unittest.TestCase):
    """Tests for the MockConnection helper used in unit tests."""

    def test_mock_initialization_sequence(self) -> None:
        mock = MockConnection()
        mock.open()

        # Test ATZ
        mock.write(b'ATZ\r')
        response = mock.read(1024).decode('ascii')
        self.assertIn('ELM327', response)

        # Test ATE0
        mock.write(b'ATE0\r')
        response = mock.read(1024).decode('ascii')
        self.assertIn('OK', response)

        # Test ATL0
        mock.write(b'ATL0\r')
        response = mock.read(1024).decode('ascii')
        self.assertIn('OK', response)

        mock.close()

    def test_mock_uds_responses(self) -> None:
        mock = MockConnection()
        mock.open()

        # Test ATSH7E4
        mock.write(b'ATSH7E4\r')
        response = mock.read(1024).decode('ascii')
        self.assertIn('OK', response)

        # Test 220102
        mock.write(b'220102\r')
        response = mock.read(2048).decode('ascii')
        self.assertIn('7EC', response)
        self.assertIn('10', response)

        mock.close()


if __name__ == '__main__':
    unittest.main()
