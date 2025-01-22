# File: hydroponic-controller/main.py

from pumps.pumps import init_pumps, pump_on, pump_off, dose_pump
from data.logger import init_logger, log_event
import time
import RPi.GPIO as GPIO


def main():
    # 1. Initialize
    init_logger()   # ensure CSV file has a header
    init_pumps()    # setup all pump pins

    try:
        # 2. Turn on pH_up pump for 2 seconds as a test
        pump_name = "pH_up"
        log_event("pump_on", pump_name)
        pump_on(pump_name)
        time.sleep(2)

        log_event("pump_off", pump_name)
        pump_off(pump_name)
        time.sleep(1)

        # 3. Use dose_pump function as well, just to show usage
        log_event("pump_dose", f"nutrientA for 3s")
        dose_pump("nutrientA", 3)
        # dose_pump logs in real system you'd do that in the function, or here after the call

        # 4. You can keep going or just exit
        print("Test complete. Check hydro_events.csv for logs.")

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
