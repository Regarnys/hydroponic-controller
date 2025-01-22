from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec
from controller.dosing_logic import simple_ph_control, simple_ec_control
from data.logger import log_sensor, log_event
from pumps.pumps import init_pumps

import time
import RPi.GPIO as GPIO

def main():
    init_pumps()

    try:
        # Example: run multiple cycles, so you see the pumps actually spin in real life
        for i in range(3):
            # 1. Mock sensor reads
            pH_val = read_ph()  # returns 5.2
            ec_val = read_ec()  # returns 0.8

            # 2. Log them (optional)
            log_sensor("pH", pH_val)
            log_sensor("EC", ec_val)
            
            # 3. Pass these fake readings into your logic
            ph_status = simple_ph_control(pH_val)
            if "Dosed" in ph_status:
                log_event("ph_control", ph_status)
            
            ec_status = simple_ec_control(ec_val)
            if "Dosed" in ec_status:
                log_event("ec_control", ec_status)
            
            # 4. Wait a bit before the next cycle
            time.sleep(10)

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
