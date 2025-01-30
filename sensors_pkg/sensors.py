#!/usr/bin/env python3
import time
import csv
import os
from datetime import datetime
from smbus2 import SMBus

class SensorReader:
    """
    A class to handle reading from two Atlas Scientific EZO sensors:
      - pH sensor at I2C address 0x63
      - EC sensor at I2C address 0x64

    Provides methods for single reads (for dashboard integration),
    as well as an optional continuous monitoring loop that logs to CSV.
    """

    def __init__(self, i2c_bus=1, ph_address=0x63, ec_address=0x64, csv_file="sensor_log.csv"):
        """
        :param i2c_bus: Which I2C bus number to use (1 on most Raspberry Pis).
        :param ph_address: 7-bit I2C address of the pH EZO circuit (default 0x63).
        :param ec_address: 7-bit I2C address of the EC EZO circuit (default 0x64).
        :param csv_file: File path/name for logging sensor data if using start_monitoring().
        """
        self.bus = SMBus(i2c_bus)
        self.ph_address = ph_address
        self.ec_address = ec_address
        self.csv_file = csv_file

    def test_i2c_devices(self):
        """
        Scan the I2C bus and see which addresses respond. Prints the results.
        Useful for debugging.
        """
        print("\nTesting I2C communication...")
        print("Scanning I2C bus for devices...")
        found_devices = []

        for addr in range(0x03, 0x78):
            try:
                self.bus.read_byte(addr)
                print("Found device at address: 0x{:02X}".format(addr))
                found_devices.append(addr)
            except:
                pass

        print("\nConfigured Addresses:")
        print("pH  sensor: 0x{:02X} {}".format(
            self.ph_address,
            "(responding)" if self.ph_address in found_devices else "(not responding)")
        )
        print("EC  sensor: 0x{:02X} {}".format(
            self.ec_address,
            "(responding)" if self.ec_address in found_devices else "(not responding)")
        )
        print("")

    def read_ph_sensor(self):
        """
        Send 'R' to pH EZO circuit, poll up to 10 times (~3s) until ready.
        Parse ASCII float from response, return pH float or None on error.

        Use this method for single pH reads in your dashboard.
        """
        try:
            # 1) Request a reading
            self.bus.write_i2c_block_data(self.ph_address, 0x00, [ord('R')])

            # 2) Poll up to 10 times, each 0.3s
            for _ in range(10):
                time.sleep(0.3)
                data = self.bus.read_i2c_block_data(self.ph_address, 0x00, 32)

                status = data[0]  # 1=success, 254=busy, 255=no data
                if status == 1:
                    ascii_bytes = []
                    for b in data[1:]:
                        if b == 0:
                            break
                        ascii_bytes.append(chr(b))
                    raw_str = "".join(ascii_bytes).strip()
                    if raw_str:
                        return float(raw_str)
                    else:
                        print("Warning: pH sensor returned empty data, retrying...")
                        continue
                elif status == 254:
                    # still processing
                    continue
                elif status == 255:
                    print("pH sensor: no data to send (status=255).")
                    return None
                else:
                    print("pH sensor error. Status byte =", status)
                    return None

            print("pH sensor timed out (never returned status=1).")
            return None

        except Exception as e:
            print("Error reading pH sensor:", e)
            return None

    def read_ec_sensor(self):
        """
        Send 'R' to EC EZO circuit, poll up to 10 times (~3s) until ready.
        Parse comma-separated ASCII (EC, TDS, SAL, SG). Return dict or None.

        This can also be called for a single read in your dashboard code.
        """
        try:
            self.bus.write_i2c_block_data(self.ec_address, 0x00, [ord('R')])

            for _ in range(10):
                time.sleep(0.3)
                data = self.bus.read_i2c_block_data(self.ec_address, 0x00, 32)
                status = data[0]  # 1=success, 254=busy, 255=no data

                if status == 1:
                    ascii_bytes = []
                    for b in data[1:]:
                        if b == 0:
                            break
                        ascii_bytes.append(chr(b))
                    raw_str = "".join(ascii_bytes).strip()

                    if not raw_str:
                        print("Warning: EC sensor returned empty data, retrying...")
                        continue

                    parts = raw_str.split(",")
                    # Typically 4 fields: EC, TDS, SAL, SG
                    if len(parts) < 1:
                        print("Warning: EC sensor response incomplete, retrying...")
                        continue

                    try:
                        ec_val  = float(parts[0]) if len(parts) > 0 else None
                        tds_val = float(parts[1]) if len(parts) > 1 else None
                        sal_val = float(parts[2]) if len(parts) > 2 else None
                        sg_val  = float(parts[3]) if len(parts) > 3 else None

                        return {
                            'ec':  ec_val,
                            'tds': tds_val,
                            'sal': sal_val,
                            'sg':  sg_val
                        }
                    except ValueError:
                        print("Error: EC sensor returned invalid data: '{}', retrying...".format(raw_str))
                        continue

                elif status == 254:
                    # still processing
                    continue
                elif status == 255:
                    print("EC sensor: no data to send (status=255).")
                    return None
                else:
                    print("EC sensor error. Status byte =", status)
                    return None

            print("EC sensor timed out (never returned status=1).")
            return None

        except Exception as e:
            print("Error reading EC sensor:", e)
            return None

    def start_monitoring(self, interval=3):
        """
        Continuously read pH and EC, print them to console,
        and log them into a CSV file named sensor_log.csv (by default).
        Press CTRL+C to stop.

        :param interval: Number of seconds to wait between sensor reads.
        """
        print("Starting sensor monitoring. Press CTRL+C to stop.")
        self.test_i2c_devices()

        # Prepare CSV file (append mode). If new, write a header row.
        file_exists = os.path.isfile(self.csv_file)
        with open(self.csv_file, mode='a', newline='') as csv_file_obj:
            writer = csv.writer(csv_file_obj)
            if not file_exists:
                # Write a header row
                writer.writerow(["Time", "pH", "EC", "TDS", "SAL", "SG"])

            print("----------------------------------------")
            print("Time                      pH       EC       TDS      SAL      SG")
            print("----------------------------------------")

            try:
                while True:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 1) Read pH
                    ph_value = self.read_ph_sensor()

                    # 2) Read EC (with TDS, SAL, SG)
                    ec_data = self.read_ec_sensor()

                    if ph_value is not None and ec_data is not None:
                        ec_val  = ec_data['ec']
                        tds_val = ec_data['tds']
                        sal_val = ec_data['sal']
                        sg_val  = ec_data['sg']

                        # Print to console
                        print("{:19s}   {:6.2f}   {:7.2f}   {:6.2f}   {:5.2f}   {:5.3f}".format(
                            timestamp,
                            ph_value,
                            ec_val if ec_val else 0,
                            tds_val if tds_val else 0,
                            sal_val if sal_val else 0,
                            sg_val if sg_val else 0
                        ))

                        # Write CSV row
                        writer.writerow([
                            timestamp,
                            "{:.2f}".format(ph_value),
                            "{:.2f}".format(ec_val if ec_val else 0),
                            "{:.2f}".format(tds_val if tds_val else 0),
                            "{:.2f}".format(sal_val if sal_val else 0),
                            "{:.3f}".format(sg_val if sg_val else 0)
                        ])
                        csv_file_obj.flush()

                    else:
                        # Print partial or no data
                        if ph_value is None:
                            print("{}   pH=NO_DATA".format(timestamp))
                        if ec_data is None:
                            print("{}   EC=NO_DATA".format(timestamp))

                    # Sleep some seconds before next read
                    time.sleep(interval)

            except KeyboardInterrupt:
                print("\nStopping sensor monitoring.")
            finally:
                self.bus.close()

    def close(self):
        """
        Close the I2C bus if needed (optional cleanup method).
        """
        self.bus.close()

# Example usage / test harness
if __name__ == "__main__":
    sensor = SensorReader()
    # For a one-time test:
    print("pH test read: ", sensor.read_ph_sensor())
    print("EC test read: ", sensor.read_ec_sensor())

    # Or run continuous monitoring
    # sensor.start_monitoring(interval=3)
    sensor.close()