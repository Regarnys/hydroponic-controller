#!/usr/bin/env python3
import time
from datetime import datetime
from atlas_i2c import AtlasI2C

class SensorReader:
    """
    A more generic class to discover and read from all Atlas Scientific
    EZO sensors on the I2C bus. This aligns with the techniques in the
    company's sample code.
    """

    def __init__(self):
        # Discover all EZO devices on the bus
        self.device_list = self._get_ezo_devices()

    def _get_ezo_devices(self):
        """
        Polls the I2C bus for addresses, sends an 'I' command to check if it's
        a recognized EZO device, and if so, queries 'name,?' to retrieve its name.
        Returns a list of AtlasI2C device objects (one for each recognized sensor).
        """
        base_device = AtlasI2C()  # A temporary device object for scanning
        addresses = base_device.list_i2c_devices()
        devices = []

        for addr in addresses:
            base_device.set_i2c_address(addr)
            response = base_device.query("I")
            try:
                # Response should look like: "EzoType,Model,Version"
                # Typically e.g.: "OK,PMP,1.0" for a pump, or "OK,EC,1.0" for an EC sensor, etc.
                parts = response.split(",")
                module_type = parts[1]  # e.g. "PH", "EC", "DO", etc.

                # Next, query the name
                name_response = base_device.query("name,?")  # e.g. "name,PH_sensor"
                name_parts = name_response.split(",")
                sensor_name = name_parts[1]  # the actual name set on the device

                # Construct a new AtlasI2C object with the known address, type, and name
                devices.append(
                    AtlasI2C(address=addr, moduletype=module_type, name=sensor_name)
                )

            except IndexError:
                # If we can't parse the response properly, it likely isn't an EZO device
                print(
                    f">> WARNING: device at I2C address {addr} not identified as an EZO sensor."
                )
                continue

        return devices

    def read_sensors(self):
        """
        Sends an 'R' (read) command to each sensor, waits an appropriate amount of time,
        and then fetches/returns the results in a dictionary keyed by sensor name.
        """
        # 1. Tell each sensor to take a reading
        for dev in self.device_list:
            dev.write("R")

        # 2. Wait for the sensors to finish their readings.
        #    Different sensors can require different wait times; you could
        #    call dev.get_command_timeout("R") for each to be precise. For
        #    pH/EC it's typically ~1.5 seconds. We'll just wait 1.5 sec.
        time.sleep(1.5)

        # 3. Read the output from each device
        readings = {}
        for dev in self.device_list:
            raw_result = dev.read().strip()

            # Parse the data depending on the sensor/module type
            if dev.moduletype.upper() == "PH":
                readings[dev.name] = self._parse_ph(raw_result)

            elif dev.moduletype.upper() == "EC":
                readings[dev.name] = self._parse_ec(raw_result)

            # Add more elifs here for other sensor types, e.g. DO, ORP, etc.

            else:
                # If you have an unknown type, just store the raw result.
                readings[dev.name] = {
                    "type": dev.moduletype,
                    "raw_data": raw_result,
                    "warning": "Unknown EZO module type",
                }

        return readings

    def _parse_ph(self, raw_result):
        """
        Expects a single float in the raw_result, e.g. '6.87'
        """
        try:
            ph_val = float(raw_result)
            return {"pH": ph_val}
        except ValueError:
            return {
                "error": f"Failed to parse pH sensor output: '{raw_result}'"
            }

    def _parse_ec(self, raw_result):
        """
        Expects a comma-separated string with 4 values:
        EC, TDS, SAL, SG
        e.g. "100.00,50.00,0.10,1.00"
        """
        parts = raw_result.split(",")
        if len(parts) != 4:
            return {"error": f"Unexpected EC response: '{raw_result}'"}

        try:
            ec_val = float(parts[0])
            tds_val = float(parts[1])
            sal_val = float(parts[2])
            sg_val = float(parts[3])
            return {
                "EC": ec_val,
                "TDS": tds_val,
                "SAL": sal_val,
                "SG": sg_val,
            }
        except ValueError:
            return {
                "error": f"Failed to parse one or more fields in EC response: '{raw_result}'"
            }


def main():
    reader = SensorReader()

    while True:
        # Grab all sensor data
        readings = reader.read_sensors()
        print(f"\n{datetime.now()} - Current Readings:")
        for sensor_name, sensor_data in readings.items():
            print(f"  {sensor_name} => {sensor_data}")

        # Sleep a bit before polling again
        time.sleep(5)

if __name__ == "__main__":
    main()
