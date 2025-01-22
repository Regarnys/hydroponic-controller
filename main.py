# File: hydroponic-controller/main.py

import time
import RPi.GPIO as GPIO

# Logging
from data.logger import init_logger, log_event, log_sensor

# Pumps
from pumps.pumps import init_pumps, pump_on, pump_off, dose_pump

# Sensors
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec

def main():
    # 1. Initialize logs and pump pins
    init_logger()   # create 'hydro_events.csv' and 'sensor_data.csv' if not present
    init_pumps()

    try:
        # 2. Read & log sensor data
        ph_val = read_ph()
        ec_val = read_ec()
        log_sensor("pH", ph_val)
        log_sensor("EC", ec_val)
        print(f"Current pH: {ph_val}, EC: {ec_val}")

        # 3. Turn on pH_up pump for 2 seconds
        log_event("pump_on", "pH_up")
        pump_on("pH_up")
        time.sleep(2)

        log_event("pump_off", "pH_up")
        pump_off("pH_up")
        time.sleep(1)

        # 4. Dose nutrientA for 3s
        log_event("pump_dose", "nutrientA for 3s")
        dose_pump("nutrientA", 3)

        # 5. Final sensor read
        ph_val_after = read_ph()
        ec_val_after = read_ec()
        log_sensor("pH", ph_val_after)
        log_sensor("EC", ec_val_after)
        print(f"After dosing, pH: {ph_val_after}, EC: {ec_val_after}")

        print("Test complete. Check 'hydro_events.csv' and 'sensor_data.csv' for logs.")

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
