#!/usr/bin/env python3
"""
Module: sensors.py
This module provides the SensorReader class to interface with Atlas Scientific sensors for pH and EC.
"""

import time
from atlas_i2c import AtlasI2C

class SensorReader:
    """
    A class for reading pH and EC values using Atlas Scientific EZO sensors.
    """

    def __init__(self, i2c_bus=1, ph_address=0x63, ec_address=0x64):
        self.ph_dev = AtlasI2C(address=ph_address, bus=i2c_bus, moduletype="PH", name="pH_sensor")
        self.ec_dev = AtlasI2C(address=ec_address, bus=i2c_bus, moduletype="EC", name="EC_sensor")
        self.wake_up_sensors()

    def wake_up_sensors(self):
        """
        Wake up sensors by sending a command to enable the LED indicator.
        """
        try:
            self.ph_dev.write("L,1")
            self.ec_dev.write("L,1")
            time.sleep(1)
        except Exception as e:
            print("Error waking up sensors:", e)

    def read_ph_sensor(self, retries=3):
        """
        Reads the pH sensor, retrying if necessary.
        Returns:
            float: pH value if successful, else None.
        """
        for attempt in range(retries):
            try:
                self.ph_dev.write("R")
                time.sleep(1.8)
                raw_response = self.ph_dev.read()
                reading_str = raw_response.split(":", 1)[-1].replace("\x00", "").strip()
                if reading_str in ["254", "255"]:
                    print(f"pH sensor status {reading_str} (Attempt {attempt+1}/{retries})... retrying.")
                    time.sleep(0.5)
                    continue
                return float(reading_str)
            except Exception as e:
                print("Error reading pH sensor:", e)
        print("pH sensor failed after multiple attempts.")
        return None

    def read_ec_sensor(self, retries=3):
        """
        Reads the EC sensor and parses its output.
        Returns:
            dict: Dictionary with keys 'ec', 'tds', 'sal', 'sg' if successful, else None.
        """
        for attempt in range(retries):
            try:
                self.ec_dev.write("R")
                time.sleep(2)
                raw_response = self.ec_dev.read()
                reading_str = raw_response.split(":", 1)[-1].replace("\x00", "").strip()
                if reading_str in ["254", "255"]:
                    print(f"EC sensor status {reading_str} (Attempt {attempt+1}/{retries})... retrying.")
                    time.sleep(0.5)
                    continue
                parts = reading_str.split(",")
                if len(parts) == 4:
                    return {
                        "ec": float(parts[0]),
                        "tds": float(parts[1]),
                        "sal": float(parts[2]),
                        "sg":  float(parts[3])
                    }
                else:
                    print(f"Unexpected EC response: {reading_str} (Attempt {attempt+1}/{retries})... retrying.")
                    time.sleep(0.5)
                    continue
            except Exception as e:
                print("Error reading EC sensor:", e)
        print("EC sensor failed after multiple attempts.")
        return None

    def close(self):
        """
        Closes the I2C connections.
        """
        self.ph_dev.close()
        self.ec_dev.close()

# **Example Test Script**
if __name__ == "__main__":
    sensor = SensorReader()
    print("==== Sensor Test ====")
    ph_val = sensor.read_ph_sensor()
    ec_data = sensor.read_ec_sensor()
    if ph_val is not None:
        print(f"pH Value: {ph_val:.2f}")
    else:
        print("pH reading failed.")
    if ec_data is not None:
        print(f"EC Value: {ec_data['ec']:.2f}")
    else:
        print("EC reading failed.")
    sensor.close()


