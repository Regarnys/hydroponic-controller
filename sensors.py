#!/usr/bin/env python3
import time
import os
from datetime import datetime
from smbus2 import SMBus

class SensorReader:
    """
    Reading from two Atlas Scientific EZO sensors (pH at 0x63, EC at 0x64).
    """

    def __init__(self, i2c_bus=1, ph_address=0x63, ec_address=0x64):
        self.bus = SMBus(i2c_bus)
        self.ph_address = ph_address
        self.ec_address = ec_address

    def read_ph_sensor(self):
        try:
            # Send "R" to request a reading
            self.bus.write_i2c_block_data(self.ph_address, 0x00, [ord('R')])
            # wait
            time.sleep(1.5)
            data = self.bus.read_i2c_block_data(self.ph_address, 0x00, 32)
            status = data[0]
            if status == 1:
                ascii_bytes = [chr(b) for b in data[1:] if b != 0]
                raw_str = "".join(ascii_bytes).strip()
                return float(raw_str) if raw_str else None
            elif status == 254:
                print("pH sensor busy (254).")
            elif status == 255:
                print("pH sensor says no data (255).")
        except Exception as e:
            print("Error reading pH sensor:", e)
        return None

    def read_ec_sensor(self):
        """
        returns dict like {"ec": float, "tds": float, "sal": float, "sg": float} or None
        """
        try:
            self.bus.write_i2c_block_data(self.ec_address, 0x00, [ord('R')])
            time.sleep(1.5)
            data = self.bus.read_i2c_block_data(self.ec_address, 0x00, 32)
            status = data[0]
            if status == 1:
                ascii_bytes = [chr(b) for b in data[1:] if b != 0]
                raw_str = "".join(ascii_bytes).strip()
                parts = raw_str.split(",")
                if len(parts) >= 4:
                    ec_val  = float(parts[0])
                    tds_val = float(parts[1])
                    sal_val = float(parts[2])
                    sg_val  = float(parts[3])
                    return {
                        "ec": ec_val,
                        "tds": tds_val,
                        "sal": sal_val,
                        "sg":  sg_val
                    }
                else:
                    print("EC sensor incomplete data:", raw_str)
            elif status == 254:
                print("EC sensor busy (254).")
            elif status == 255:
                print("EC sensor says no data (255).")
        except Exception as e:
            print("Error reading EC sensor:", e)
        return None

    def close(self):
        self.bus.close()
