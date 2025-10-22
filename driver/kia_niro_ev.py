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

        # Enable cyclic Tester Present to keep ECU awake during diagnostics
        # TEMPORARILY DISABLED for debugging
        # try:
        #     # Default 2s interval (ELM327 will send 0x3E 0x00)
        #     self.elm.enable_cyclic_tester_present(2.0)
        # except Exception:
        #     # Non-fatal: some tests or mock connections may not implement this
        #     pass

        # Retry configuration (can be tuned if needed)
        self._read_retries = 5  # Increased from 3 to 5
        self._read_backoff = 0.25  # seconds between retries
        self._debug = False  # Set to True for verbose logging

        # Longer startup delay to ensure ECU is awake and protocol is established
        try:
            import time as _time
            _time.sleep(3.0)  # 3 seconds for ECU wake-up and protocol detection
        except Exception:
            pass

        # Send a warmup request to establish the connection and wake the ECU
        try:
            if self._debug:
                print("[DEBUG] Sending warmup request to establish ECU connection...")
            # Try to read SOC - this will establish the protocol
            warmup_response = self.elm.send_message(self.bms_can_id, (self.READ_DATA_BY_ID << 16) | self.PID_BMS_MAIN)
            if self._debug:
                print(f"[DEBUG] Warmup successful, ECU responding (payload: {len(warmup_response.payload)} bytes)")
            import time as _time
            _time.sleep(0.5)  # Brief pause after warmup
        except Exception as e:
            if self._debug:
                print(f"[DEBUG] Warmup failed: {e} (will retry on first real request)")
            pass

    def _read_bms_data(self, pid: int) -> bytearray:
        import time

        uds_command = (self.READ_DATA_BY_ID << 16) | pid
        
        if self._debug:
            print(f"[DEBUG] Reading BMS PID 0x{pid:04X}, UDS command: 0x{uds_command:06X}")

        last_exc = None
        for attempt in range(1, self._read_retries + 1):
            try:
                if self._debug:
                    print(f"[DEBUG] Attempt {attempt}/{self._read_retries}")
                
                # Only flush on retry attempts (not first attempt)
                if attempt > 1:
                    try:
                        self.elm.connection.flush_input()
                        if self._debug:
                            print(f"[DEBUG] Flushed input buffer before retry")
                        # Small delay after flush for BLE to stabilize
                        if hasattr(self.elm.connection, '_read_buffer'):
                            time.sleep(0.15)
                    except Exception:
                        pass
                
                response = self.elm.send_message(self.bms_can_id, uds_command)
                
                if self._debug:
                    print(f"[DEBUG] Received payload length: {len(response.payload)} bytes")
                    print(f"[DEBUG] Payload: {response.payload.hex()}")
                    if len(response.payload) < 10:
                        print(f"[DEBUG] WARNING: Unusually short payload - possible communication issue")
                
                return response.payload
            except Exception as e:
                last_exc = e
                if self._debug:
                    print(f"[DEBUG] Attempt {attempt} failed: {type(e).__name__}: {e}")
                
                # If this was the last attempt, re-raise
                if attempt == self._read_retries:
                    if self._debug:
                        print(f"[DEBUG] All {self._read_retries} attempts exhausted, raising exception")
                    raise
                
                # Backoff before retrying
                backoff_time = self._read_backoff * attempt
                if self._debug:
                    print(f"[DEBUG] Waiting {backoff_time}s before retry...")
                try:
                    time.sleep(backoff_time)
                except Exception:
                    pass

        # If somehow we exit loop without returning, raise last exception
        if last_exc:
            raise last_exc
        raise RuntimeError("Unknown error reading BMS data")

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
