# File: sensors.py

import time
from atlas_i2c import AtlasI2C  # or from .atlas_i2c import AtlasI2C if local
# or "from AtlasI2C import AtlasI2C" if your module is named exactly that

class SensorReader:
    """
    Updated to use AtlasI2C internally but still accept (i2c_bus, ph_address, ec_address)
    and provide read_ph_sensor() and read_ec_sensor() methods.
    """

    def __init__(self, i2c_bus=1, ph_address=0x63, ec_address=0x64):
        # Create AtlasI2C objects for each sensor
        self.ph_dev = AtlasI2C(address=ph_address, bus=i2c_bus, moduletype="PH", name="pH_sensor")
        self.ec_dev = AtlasI2C(address=ec_address, bus=i2c_bus, moduletype="EC", name="EC_sensor")

    def read_ph_sensor(self):
        """
        Send 'R' command to the pH device and parse the float response.
        """
        try:
            self.ph_dev.write("R")
            time.sleep(1.5)  # let it process
            raw_response = self.ph_dev.read()  # e.g. "Success pH_sensor: 6.87"
            # Typically, the part after the colon is your actual reading.
            # Let's parse that:
            reading_str = raw_response.split(":")[-1].strip()  # e.g. "6.87"
            return float(reading_str) if reading_str else None
        except Exception as e:
            print("Error reading pH sensor:", e)
            return None

    def read_ec_sensor(self):
        """
        For EC: typically we get 4 comma-separated values: EC, TDS, SAL, SG.
        We'll parse them into a dict, e.g. {"ec": float, "tds": float, "sal": float, "sg": float}.
        """
        try:
            self.ec_dev.write("R")
            time.sleep(1.5)
            raw_response = self.ec_dev.read()  # e.g. "Success EC_sensor: 100.00,50.00,0.10,1.00"
            # extract the raw numeric string
            numeric_part = raw_response.split(":")[-1].strip()  # "100.00,50.00,0.10,1.00"
            parts = numeric_part.split(",")
            if len(parts) == 4:
                ec_val  = float(parts[0])
                tds_val = float(parts[1])
                sal_val = float(parts[2])
                sg_val  = float(parts[3])
                return {"ec": ec_val, "tds": tds_val, "sal": sal_val, "sg": sg_val}
            else:
                print("Unexpected EC response:", numeric_part)
                return None
        except Exception as e:
            print("Error reading EC sensor:", e)
            return None

