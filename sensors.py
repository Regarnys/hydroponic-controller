#!/usr/bin/env python3

import time
from atlas_i2c import AtlasI2C  # Adjust if your file is named differently

class SensorReader:
    """
    A sensor-reading class that communicates with two Atlas Scientific EZO
    circuits (pH and EC). It uses the AtlasI2C driver, handles null-terminations,
    and checks the sensor status codes before converting to floats.
    """

    def __init__(self, i2c_bus=1, ph_address=0x63, ec_address=0x64):
        """
        :param i2c_bus: Which I2C bus to use (default 1 on Raspberry Pi).
        :param ph_address: I2C address for the pH sensor (default 0x63).
        :param ec_address: I2C address for the EC sensor (default 0x64).
        """
        # Create two AtlasI2C device objects, one for pH, one for EC
        self.ph_dev = AtlasI2C(address=ph_address, bus=i2c_bus, moduletype="PH", name="pH_sensor")
        self.ec_dev = AtlasI2C(address=ec_address, bus=i2c_bus, moduletype="EC", name="EC_sensor")

    def read_ph_sensor(self):
        """
        Sends an 'R' (read) command to the pH device, then parses the returned float.
        If status = 254/255 or if parsing fails, returns None.
        """
        try:
            # 1) Request a reading
            self.ph_dev.write("R")
            time.sleep(1.5)  # allow the sensor time to process

            # 2) Read the raw string from the device
            raw_response = self.ph_dev.read()  
            # e.g. "Success pH_sensor: 7.936\x00\x00\x00..." or "Error pH_sensor: 255"

            # 3) Extract just what's after the colon
            #    e.g. "7.936\x00\x00\x00..."
            reading_str = raw_response.split(":", 1)[-1]
            # Remove null chars, strip whitespace
            reading_str = reading_str.replace("\x00", "").strip()

            # 4) Check for known "no data" status codes
            if reading_str in ["254", "255"]:
                # 254 => busy, 255 => no data
                print("pH sensor returned status", reading_str, "=> skipping reading.")
                return None

            # 5) Convert to float
            return float(reading_str)

        except Exception as e:
            print("Error reading pH sensor:", e)
            return None

    def read_ec_sensor(self):
        """
        Sends an 'R' command to the EC device, which typically returns 4 comma-separated values:
          EC, TDS, SAL, SG
        Example: "Success EC_sensor: 100.00,50.00,0.10,1.00"
        If the device is busy or has no data, we might see "254" / "255" or partial results.
        Returns a dict: {"ec": float, "tds": float, "sal": float, "sg": float} or None if error.
        """
        try:
            # 1) Request a reading
            self.ec_dev.write("R")
            time.sleep(1.5)

            # 2) Read the raw string
            raw_response = self.ec_dev.read()
            # e.g. "Success EC_sensor: 100.00,50.00,0.10,1.00"
            # or "Success EC_sensor: 255"

            # 3) Get everything after the colon, remove nulls, strip
            reading_str = raw_response.split(":", 1)[-1]
            reading_str = reading_str.replace("\x00", "").strip()

            # 4) Check status
            if reading_str in ["254", "255"]:
                print("EC sensor returned status", reading_str, "=> skipping reading.")
                return None

            # 5) Parse comma-separated fields
            parts = reading_str.split(",")
            if len(parts) == 4:
                ec_val  = float(parts[0])
                tds_val = float(parts[1])
                sal_val = float(parts[2])
                sg_val  = float(parts[3])
                return {"ec": ec_val, "tds": tds_val, "sal": sal_val, "sg": sg_val}
            else:
                print("Unexpected EC response:", reading_str)
                return None

        except Exception as e:
            print("Error reading EC sensor:", e)
            return None

    def close(self):
        """
        Closes I2C file handles. Call this when you're done if needed.
        """
        self.ph_dev.close()
        self.ec_dev.close()


