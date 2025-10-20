"""
Kia Niro EV diagnostic module.

This module provides high-level access to Kia Niro EV specific diagnostic data
using UDS (Unified Diagnostic Services) over ISO-TP protocol.

Based on diagnostic specifications from:
https://github.com/JejuSoul/OBD-PIDs-for-HKMC-EVs
"""

from .elm327 import ELM327


class KiaNiroEV:
    """
    Kia Niro EV diagnostic interface.
    
    Provides methods to read various battery and vehicle parameters from the
    Battery Management System (BMS) via UDS commands.
    
    Attributes:
        elm (ELM327): Connected ELM327 interface instance.
        bms_can_id (int): CAN ID for BMS module (0x7E4 for requests, 0x7EC for responses).
    """
    
    # CAN IDs
    BMS_REQUEST_ID = 0x7E4
    BMS_RESPONSE_ID = 0x7EC
    
    # UDS Service IDs
    READ_DATA_BY_ID = 0x22
    
    # PID definitions for BMS
    PID_BMS_MAIN = 0x0101  # Main BMS data
    PID_CELL_VOLTAGES_1 = 0x0102  # Cell voltages 1-32
    PID_CELL_VOLTAGES_2 = 0x0103  # Cell voltages 33-64
    PID_CELL_VOLTAGES_3 = 0x0104  # Cell voltages 65-96
    PID_CELL_VOLTAGES_4 = 0x0105  # Cell voltages 97-98 and other data
    
    def __init__(self, elm: ELM327) -> None:
        """
        Initialize Kia Niro EV interface.
        
        Args:
            elm (ELM327): Already connected ELM327 instance.
        """
        self.elm = elm
        self.bms_can_id = self.BMS_REQUEST_ID
    
    async def _read_bms_data(self, pid: int) -> bytearray:
        """
        Read data from BMS module.
        
        Args:
            pid (int): Parameter ID to read.
            
        Returns:
            bytearray: Response payload data.
        """
        # Construct UDS command: 22 (ReadDataByIdentifier) + PID (2 bytes)
        uds_command = (self.READ_DATA_BY_ID << 16) | pid
        response = await self.elm.send_message(self.bms_can_id, uds_command)
        return response.payload
    
    async def get_soc(self) -> float:
        """
        Get State of Charge from BMS.
        
        Returns:
            float: State of Charge in percent (0-100%).
        """
        data = await self._read_bms_data(self.PID_BMS_MAIN)
        # SOC BMS is at byte position 4 (e in CSV notation), formula: e/2
        if len(data) < 5:
            raise ValueError("Invalid BMS response: insufficient data")
        soc_raw = data[4]
        return soc_raw / 2.0
    
    async def get_cell_voltage(self, cell: int) -> float:
        """
        Get voltage of a specific battery cell.
        
        The Kia Niro EV has 98 battery cells numbered 1-98.
        
        Args:
            cell (int): Cell number (1-98).
            
        Returns:
            float: Cell voltage in volts.
            
        Raises:
            ValueError: If cell number is out of range.
        """
        if cell < 1 or cell > 98:
            raise ValueError(f"Cell number must be between 1 and 98, got {cell}")
        
        # Determine which PID contains this cell's data
        if cell <= 32:
            # Cells 1-32 are in PID 0x0102
            data = await self._read_bms_data(self.PID_CELL_VOLTAGES_1)
            byte_index = cell + 3  # Cells start at byte 4 (e), cell 1 at index 4
        elif cell <= 64:
            # Cells 33-64 are in PID 0x0103
            data = await self._read_bms_data(self.PID_CELL_VOLTAGES_2)
            byte_index = (cell - 32) + 3
        elif cell <= 96:
            # Cells 65-96 are in PID 0x0104
            data = await self._read_bms_data(self.PID_CELL_VOLTAGES_3)
            byte_index = (cell - 64) + 3
        else:
            # Cells 97-98 are in PID 0x0105
            data = await self._read_bms_data(self.PID_CELL_VOLTAGES_4)
            # Cell 97 is at ai (byte 34), Cell 98 is at aj (byte 35)
            byte_index = (cell - 97) + 34
        
        if len(data) <= byte_index:
            raise ValueError(f"Invalid response: insufficient data for cell {cell}")
        
        # Formula from CSV: cell_value/50
        voltage_raw = data[byte_index]
        return voltage_raw / 50.0
    
    async def get_battery_voltage(self) -> float:
        """
        Get main battery DC voltage.
        
        Returns:
            float: Battery voltage in volts.
        """
        data = await self._read_bms_data(self.PID_BMS_MAIN)
        # Battery DC Voltage: ((m<<8)+n)/10, bytes at positions 12 and 13
        if len(data) < 14:
            raise ValueError("Invalid BMS response: insufficient data")
        voltage_raw = (data[12] << 8) | data[13]
        return voltage_raw / 10.0
    
    async def get_battery_current(self) -> float:
        """
        Get battery current.
        
        Returns:
            float: Battery current in amperes (negative = charging, positive = discharging).
        """
        data = await self._read_bms_data(self.PID_BMS_MAIN)
        # Battery Current: ((Signed(K)*256)+L)/10, bytes at positions 10 and 11
        if len(data) < 12:
            raise ValueError("Invalid BMS response: insufficient data")
        
        # Handle signed byte
        current_high = data[10]
        if current_high > 127:
            current_high = current_high - 256
        
        current_raw = (current_high * 256) + data[11]
        return current_raw / 10.0
    
    async def get_max_cell_voltage(self) -> tuple[float, int]:
        """
        Get maximum cell voltage and cell number.
        
        Returns:
            tuple[float, int]: (voltage in volts, cell number).
        """
        data = await self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 26:
            raise ValueError("Invalid BMS response: insufficient data")
        
        # Max Cell Voltage: x/50 (byte 23)
        # Max Cell Voltage No: y (byte 24)
        voltage = data[23] / 50.0
        cell_no = data[24]
        return (voltage, cell_no)
    
    async def get_min_cell_voltage(self) -> tuple[float, int]:
        """
        Get minimum cell voltage and cell number.
        
        Returns:
            tuple[float, int]: (voltage in volts, cell number).
        """
        data = await self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 27:
            raise ValueError("Invalid BMS response: insufficient data")
        
        # Min Cell Voltage: z/50 (byte 25)
        # Min Cell Voltage No: aa (byte 26)
        voltage = data[25] / 50.0
        cell_no = data[26]
        return (voltage, cell_no)
    
    async def get_soh(self) -> float:
        """
        Get State of Health from BMS.
        
        Returns:
            float: State of Health in percent (0-100%).
        """
        data = await self._read_bms_data(self.PID_CELL_VOLTAGES_4)
        if len(data) < 28:
            raise ValueError("Invalid BMS response: insufficient data")
        
        # SOH: ((z<<8)+aa)/10 (bytes 25 and 26 in PID 0x0105)
        soh_raw = (data[25] << 8) | data[26]
        return soh_raw / 10.0
    
    async def get_battery_temperatures(self) -> dict[str, float]:
        """
        Get battery temperature readings.
        
        Returns:
            dict[str, float]: Dictionary with temperature values in Celsius:
                - 'max': Maximum battery temperature
                - 'min': Minimum battery temperature
                - 'inlet': Battery inlet temperature
                - 'module_01' through 'module_04': Individual module temperatures
        """
        data = await self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 21:
            raise ValueError("Invalid BMS response: insufficient data")
        
        def signed_byte(value: int) -> int:
            """Convert unsigned byte to signed."""
            return value if value < 128 else value - 256
        
        return {
            'max': signed_byte(data[14]),  # Byte O (14)
            'min': signed_byte(data[15]),  # Byte P (15)
            'module_01': signed_byte(data[16]),  # Byte Q (16)
            'module_02': signed_byte(data[17]),  # Byte R (17)
            'module_03': signed_byte(data[18]),  # Byte S (18)
            'module_04': signed_byte(data[19]),  # Byte T (19)
            'inlet': signed_byte(data[22]),  # Byte W (22)
        }
