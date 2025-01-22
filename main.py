#!/usr/bin/env python3
import time
import RPi.GPIO as GPIO

from data.logger import init_logger, log_event, log_sensor
from pumps.pumps import init_pumps, pump_on, pump_off
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec

def main():
    # 1. Initialize logs and pump pins
    init_logger()       # ensures the CSV files exist with headers
    init_pumps()        # configure GPIO for all five pumps

    try:
        # 2. Quick test of all five pumps
        pump_names = ["pH_up", "pH_down", "nutrientA", "nutrientB", "nutrientC"]
        for pump in pump_names:
            # Log that we are turning this pump on
            log_event("pump_on", pump)
            print(f"Turning ON {pump} for 2s...")
            pump_on(pump)
            time.sleep(2)

            # Now turn it off
            log_event("pump_off", pump)
            print(f"Turning OFF {pump}...")
            pump_off(pump)
            time.sleep(1)

        # 3. Read & log sensor data (pH, EC)
        ph_val = read_ph()
        ec_val = read_ec()
        log_sensor("pH", ph_val)
        log_sensor("EC", ec_val)
        print(f"Sensor readings: pH={ph_val}, EC={ec_val}")

        print("All pump tests complete. Sensor data logged. Check CSV files.")

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
