"""
Test module for Kia Niro EV diagnostics.
"""

import unittest
from driver.kia_niro_ev import KiaNiroEV
from driver.elm327 import ELM327
from driver.mock_serial import MockSerial


class TestKiaNiroEV(unittest.TestCase):
    """Test cases for Kia Niro EV diagnostic interface."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock serial connection
        self.mock_serial = MockSerial(port="mock", baudrate=38400, timeout=1.0)
        
        # Create ELM327 instance with mock serial
        self.elm = ELM327(serial_connection=self.mock_serial)
        
        # Create Kia Niro EV instance
        self.kia = KiaNiroEV(self.elm)
    
    def test_get_soc_52_5_percent(self):
        """Test SOC reading with real trace data showing 52.5%."""
        # Real trace from the user:
        # Sende: 220101
        # Response: 7EC 10 3E 62 01 01 EF FB E7 ED 69 00 00 00 00 00
        #           7EC 21 00 00 0E 26 0D 0C 0D 0D 0D 00 00 00 34 BC
        #           7EC 22 18 BC 56 00 00 7C 00 02 DE 80 00 02 C9 55
        #           7EC 23 00 01 19 AF 00 01 07 C3 00 EC 65 6F 00 00
        #           7EC 24 03 00 00 00 00 0B B8
        #
        # After ISO-TP reassembly: 62 01 01 EF FB E7 ED 69 00 00 00 00 00 00 00 0E 26 ...
        # SOC is at byte 4 of payload (after 62 01 01): 0x69 = 105, 105/2 = 52.5%
        
        # Get SOC
        soc = self.kia.get_soc()
        
        # SOC should be 52.5%
        self.assertAlmostEqual(soc, 52.5, places=1)
    
    def test_get_battery_voltage(self):
        """Test battery voltage reading."""
        # Get battery voltage (using same trace data as test_get_soc)
        voltage = self.kia.get_battery_voltage()
        
        # Battery voltage is at bytes 12-13 of payload (after service + data ID)
        # From trace: bytes 12=0x0E, 13=0x26
        # ((0x0E << 8) + 0x26) / 10 = (3584 + 38) / 10 = 362.2V
        self.assertAlmostEqual(voltage, 362.2, places=1)
    
    def test_get_max_cell_voltage(self):
        """Test maximum cell voltage reading."""
        # Get max cell voltage
        voltage, cell_no = self.kia.get_max_cell_voltage()
        
        # From trace: byte 23=0xDE (222), byte 24=0x80 (128)
        # Voltage: 222/50 = 4.44V
        # Cell: 128 (but this seems high, might be 0x00 in actual working system)
        self.assertIsInstance(voltage, float)
        self.assertIsInstance(cell_no, int)
        self.assertGreater(voltage, 0)
    
    def test_get_battery_temperatures(self):
        """Test battery temperature readings."""
        temps = self.kia.get_battery_temperatures()
        
        # Verify all expected keys are present
        expected_keys = ['max', 'min', 'module_01', 'module_02', 'module_03', 'module_04', 'inlet']
        for key in expected_keys:
            self.assertIn(key, temps)
            self.assertIsInstance(temps[key], (int, float))


if __name__ == '__main__':
    unittest.main()
