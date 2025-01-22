# File: data/logger.py

import os
import datetime

EVENT_LOGFILE = "hydro_events.csv"
SENSOR_LOGFILE = "sensor_data.csv"

def init_logger():
    """
    Initialize event and sensor CSVs if they don't exist.
    """
    if not os.path.isfile(EVENT_LOGFILE):
        with open(EVENT_LOGFILE, "w", encoding="utf-8") as f:
            f.write("timestamp,event,details\n")

    if not os.path.isfile(SENSOR_LOGFILE):
        with open(SENSOR_LOGFILE, "w", encoding="utf-8") as f:
            f.write("timestamp,sensor_name,value\n")

def log_event(event, details=""):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(EVENT_LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"{now_str},{event},{details}\n")

def log_sensor(sensor_name, value):
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(SENSOR_LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"{now_str},{sensor_name},{value}\n")


if __name__ == "__main__":
    main()
