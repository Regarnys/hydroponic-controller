#!/usr/bin/env python3

import time
from atlas_i2c import AtlasI2C  # Uses the Atlas I2C driver

class SensorReader:
    """
    A class for reading pH and EC values using Atlas Scientific EZO sensors.
    Uses the AtlasI2C driver, checks sensor status, and handles formatting.
    """

    def __init__(self, i2c_bus=1, ph_address=0x63, ec_address=0x64):
        """
        :param i2c_bus: The I2C bus to use (default 1 on Raspberry Pi).
        :param ph_address: The I2C address for the pH sensor (default 0x63).
        :param ec_address: The I2C address for the EC sensor (default 0x64).
        """
        self.ph_dev = AtlasI2C(address=ph_address, bus=i2c_bus, moduletype="PH", name="pH_sensor")
        self.ec_dev = AtlasI2C(address=ec_address, bus=i2c_bus, moduletype="EC", name="EC_sensor")

        # Wake up sensors on startup
        self.wake_up_sensors()

    def wake_up_sensors(self):
        """
        Sends a wake-up command to ensure sensors are ready.
        Atlas sensors sometimes go into sleep mode when idle.
        """
        try:
            self.ph_dev.write("L,1")  # Enable LED (indicates sensor is awake)
            self.ec_dev.write("L,1")
            time.sleep(1)  # Allow time to wake up
        except Exception as e:
            print("Error waking up sensors:", e)

    def read_ph_sensor(self, retries=3):
        """
        Reads pH sensor value. If busy or no data (status 254/255), retries.
        Returns a float pH value or None if error.
        """
        for attempt in range(retries):
            try:
                self.ph_dev.write("R")  # Send read command
                time.sleep(1.8)  # Allow processing time

                raw_response = self.ph_dev.read()
                reading_str = raw_response.split(":", 1)[-1].replace("\x00", "").strip()

                # Handle error codes
                if reading_str in ["254", "255"]:
                    print(f"pH sensor status {reading_str} (Attempt {attempt+1}/{retries})... retrying.")
                    time.sleep(0.5)
                    continue  # Retry

                return float(reading_str)

            except Exception as e:
                print("Error reading pH sensor:", e)

        print("pH sensor failed after multiple attempts.")
        return None

    def read_ec_sensor(self, retries=3):
        """
        Reads EC sensor value. Parses EC, TDS, SAL, SG.
        Returns a dictionary {ec, tds, sal, sg} or None if error.
        """
        for attempt in range(retries):
            try:
                self.ec_dev.write("R")
                time.sleep(2)  # Allow processing time

                raw_response = self.ec_dev.read()
                reading_str = raw_response.split(":", 1)[-1].replace("\x00", "").strip()

                # Handle error codes
                if reading_str in ["254", "255"]:
                    print(f"EC sensor status {reading_str} (Attempt {attempt+1}/{retries})... retrying.")
                    time.sleep(0.5)
                    continue  # Retry

                # Parse comma-separated values (EC, TDS, SAL, SG)
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
                    continue  # Retry

            except Exception as e:
                print("Error reading EC sensor:", e)

        print("EC sensor failed after multiple attempts.")
        return None

    def close(self):
        """
        Closes I2C connections. Use this when done.
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



