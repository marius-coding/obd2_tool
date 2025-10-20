"""
Kia Niro EV diagnostic module.

This module provides high-level access to Kia Niro EV specific diagnostic data
using UDS (Unified Diagnostic Services) over ISO-TP protocol.

Based on diagnostic specifications from:
https://github.com/JejuSoul/OBD-PIDs-for-HKMC-EVs
"""

from .elm327 import ELM327


from .elm327 import ELM327


class KiaNiroEV:
    """Kia Niro EV diagnostic interface (synchronous).

    Methods perform synchronous requests using an already-configured ELM327
    instance. They return parsed payloads or computed values.
    """

    BMS_REQUEST_ID = 0x7E4
    BMS_RESPONSE_ID = 0x7EC
    READ_DATA_BY_ID = 0x22

    PID_BMS_MAIN = 0x0101
    PID_CELL_VOLTAGES_1 = 0x0102
    PID_CELL_VOLTAGES_2 = 0x0103
    PID_CELL_VOLTAGES_3 = 0x0104
    PID_CELL_VOLTAGES_4 = 0x0105

    def __init__(self, elm: ELM327) -> None:
        self.elm = elm
        self.bms_can_id = self.BMS_REQUEST_ID

    def _read_bms_data(self, pid: int) -> bytearray:
        uds_command = (self.READ_DATA_BY_ID << 16) | pid
        response = self.elm.send_message(self.bms_can_id, uds_command)
        return response.payload

    def get_soc(self) -> float:
        data = self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 5:
            raise ValueError("Invalid BMS response: insufficient data")
        soc_raw = data[4]
        return soc_raw / 2.0

    def get_cell_voltage(self, cell: int) -> float:
        if cell < 1 or cell > 98:
            raise ValueError(f"Cell number must be between 1 and 98, got {cell}")

        if cell <= 32:
            data = self._read_bms_data(self.PID_CELL_VOLTAGES_1)
            byte_index = cell + 3
        elif cell <= 64:
            data = self._read_bms_data(self.PID_CELL_VOLTAGES_2)
            byte_index = (cell - 32) + 3
        elif cell <= 96:
            data = self._read_bms_data(self.PID_CELL_VOLTAGES_3)
            byte_index = (cell - 64) + 3
        else:
            data = self._read_bms_data(self.PID_CELL_VOLTAGES_4)
            byte_index = (cell - 97) + 34

        if len(data) <= byte_index:
            raise ValueError(f"Invalid response: insufficient data for cell {cell}")
        return data[byte_index] / 50.0

    def get_battery_voltage(self) -> float:
        data = self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 14:
            raise ValueError("Invalid BMS response: insufficient data")
        voltage_raw = (data[12] << 8) | data[13]
        return voltage_raw / 10.0

    def get_battery_current(self) -> float:
        data = self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 12:
            raise ValueError("Invalid BMS response: insufficient data")
        current_high = data[10]
        if current_high > 127:
            current_high = current_high - 256
        current_raw = (current_high * 256) + data[11]
        return current_raw / 10.0

    def get_max_cell_voltage(self) -> tuple[float, int]:
        data = self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 26:
            raise ValueError("Invalid BMS response: insufficient data")
        voltage = data[23] / 50.0
        cell_no = data[24]
        return (voltage, cell_no)

    def get_min_cell_voltage(self) -> tuple[float, int]:
        data = self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 27:
            raise ValueError("Invalid BMS response: insufficient data")
        voltage = data[25] / 50.0
        cell_no = data[26]
        return (voltage, cell_no)

    def get_soh(self) -> float:
        data = self._read_bms_data(self.PID_CELL_VOLTAGES_4)
        if len(data) < 28:
            raise ValueError("Invalid BMS response: insufficient data")
        soh_raw = (data[25] << 8) | data[26]
        return soh_raw / 10.0

    def get_battery_temperatures(self) -> dict[str, float]:
        data = self._read_bms_data(self.PID_BMS_MAIN)
        if len(data) < 21:
            raise ValueError("Invalid BMS response: insufficient data")

        def signed_byte(value: int) -> int:
            return value if value < 128 else value - 256

        return {
            'max': signed_byte(data[14]),
            'min': signed_byte(data[15]),
            'module_01': signed_byte(data[16]),
            'module_02': signed_byte(data[17]),
            'module_03': signed_byte(data[18]),
            'module_04': signed_byte(data[19]),
            'inlet': signed_byte(data[22]),
    }
