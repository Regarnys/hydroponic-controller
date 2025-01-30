# File: data/logger.py

import os
import time
import datetime

EVENT_LOG = os.path.join(os.path.dirname(__file__), "hydro_events.csv")
SENSOR_LOG = os.path.join(os.path.dirname(__file__), "sensor_data.csv")

def init_event_log():
    # Create hydro_events.csv with header if not existing
    if not os.path.isfile(EVENT_LOG):
        with open(EVENT_LOG, "w", encoding="utf-8") as f:
            f.write("timestamp,event,details\n")

def init_sensor_log():
    # Create sensor_data.csv with header if not existing
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

def start_continuous_logging(sensor, interval=10):
    """
    Continuously read pH & EC from the given sensor object and log to sensor_data.csv.
    This reuses log_sensor(...) to append data indefinitely.
    Press Ctrl+C to stop.

    :param sensor: An object with methods read_ph_sensor() and read_ec_sensor().
                   Typically an instance of your SensorReader class.
    :param interval: Delay (seconds) between consecutive sensor reads.
    """
    init_sensor_log()  # ensure sensor_data.csv exists with a header
    print("Starting continuous sensor logging. Press Ctrl+C to stop.")

    try:
        while True:
            # 1) Read pH
            ph_val = sensor.read_ph_sensor()
            if ph_val is not None:
                log_sensor("pH", "{:.2f}".format(ph_val))

            # 2) Read EC dictionary
            ec_result = sensor.read_ec_sensor()  # e.g. {"ec":..., "tds":..., "sal":..., "sg":...}
            if ec_result and ec_result.get("ec") is not None:
                ec_val = ec_result["ec"]
                log_sensor("EC", "{:.2f}".format(ec_val))
                # optionally also log TDS, SAL, SG if you want in the same file
                # log_sensor("TDS", "{:.2f}".format(ec_result["tds"]))
                # log_sensor("SAL", "{:.2f}".format(ec_result["sal"]))
                # log_sensor("SG",  "{:.2f}".format(ec_result["sg"]))

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped continuous logging.")
    finally:
        # If your sensor object supports a .close() method, you can call it here
        if hasattr(sensor, "close"):
            sensor.close()
