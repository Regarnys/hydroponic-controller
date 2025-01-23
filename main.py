# main.py
import time
import RPi.GPIO as GPIO

from data.logger import init_logger, log_event, log_sensor
from pumps.pumps import init_pumps
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec
from controller.dosing_logic import simple_ph_control, simple_ec_control

def main():
    init_logger()
    init_pumps()

    try:
        while True:
            pH_val = read_ph()   # mock or real
            ec_val = read_ec()   # mock or real

            log_sensor("pH", pH_val)
            log_sensor("EC", ec_val)

            # pH logic
            ph_status = simple_ph_control(pH_val)
            if "Dosed" in ph_status or "limit reached" in ph_status:
                log_event("ph_control", ph_status)

            # EC logic
            ec_status = simple_ec_control(ec_val)
            if "Dosed" in ec_status or "limit reached" in ec_status:
                log_event("ec_control", ec_status)

            time.sleep(300)  # wait 5 minutes
    except KeyboardInterrupt:
        print("Interrupted.")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()

