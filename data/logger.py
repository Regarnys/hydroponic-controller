# File: hydroponic-controller/data/logger.py

import time
import os

LOGFILE = "hydro_events.csv"

def init_logger():
    """
    If the CSV doesn't exist, create it with a header row.
    """
    if not os.path.isfile(LOGFILE):
        with open(LOGFILE, "w") as f:
            f.write("timestamp,event,details\n")

def log_event(event, details=""):
    """
    Append a single line to the CSV:
      timestamp,event,details
    """
    now = time.time()
    with open(LOGFILE, "a") as f:
        f.write(f"{now},{event},{details}\n")
