# File: hydroponic-controller/main.py

import time
import RPi.GPIO as GPIO

from data.logger import init_logger, log_event
from pumps.pumps import (
    init_pumps,
    pump_on,
    pump_off,
    dose_pump
)

def main():
    # 1. Initialize logging and pumps
    init_logger()   # Ensure 'hydro_events.csv' has header
    init_pumps()    # Setup all pump GPIO pins

    try:
        # 2. Turn on pH_up pump for 2 seconds
        log_event("pump_on", "pH_up")
        pump_on("pH_up")
        time.sleep(2)

        log_event("pump_off", "pH_up")
        pump_off("pH_up")
        time.sleep(1)

        # 3. Demonstrate dose_pump usage for nutrientA
        log_event("pump_dose", "nutrientA for 3s")
        dose_pump("nutrientA", 3)
        # dose_pump calls pump_on + time.sleep + pump_off internally

        print("Test complete. Check 'hydro_events.csv' for logs.")

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        GPIO.cleanup()  # Release GPIO pins

if __name__ == "__main__":
    main()
