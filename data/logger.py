# File: data/logger.py

import os
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
        f.write(f"{now_str},{event},{details}\n")

def log_sensor(sensor_name, value):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SENSOR_LOG, "a", encoding="utf-8") as f:
        f.write(f"{now_str},{sensor_name},{value}\n")
