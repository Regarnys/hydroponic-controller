# File: data/logger.py

import os
import time
import datetime
from smbus2 import SMBus

EVENT_LOG = os.path.join(os.path.dirname(__file__), "hydro_events.csv")
SENSOR_LOG = os.path.join(os.path.dirname(__file__), "sensor_data.csv")

def init_event_log():
    if not os.path.isfile(EVENT_LOG):
        with open(EVENT_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp,event,details\n")

def init_sensor_log():
    if not os.path.isfile(SENSOR_LOG):
        with open(SENSOR_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp,sensor_name,value\n")

def log_event(event, details=""):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(EVENT_LOG, "a", encoding="utf-8") as f:
        f.write("{},{},{}\n".format(now_str, event, details))

def log_sensor(sensor_name, value):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SENSOR_LOG, "a", encoding="utf-8") as f:
        f.write("{},{},{}\n".format(now_str, sensor_name, value))

def start_continuous_logging(sensor_obj, interval=10):
    """
    Run in a background thread to continuously read pH & EC from 'sensor_obj'
    every 'interval' seconds and log to sensor_data.csv.
    """
    init_sensor_log()
    print("Starting continuous sensor logging. Press Ctrl+C to stop.")
    try:
        while True:
            # 1) read pH
            ph_val = sensor_obj.read_ph_sensor()
            if ph_val is not None:
                log_sensor("pH", "{:.2f}".format(ph_val))

            # 2) read EC
            ec_dict = sensor_obj.read_ec_sensor()  # e.g. {"ec":..., "tds":..., ...}
            if ec_dict and ec_dict.get("ec") is not None:
                ec_val = ec_dict["ec"]
                log_sensor("EC", "{:.2f}".format(ec_val))

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped continuous logging.")
    finally:
        if hasattr(sensor_obj, "close"):
            sensor_obj.close()
