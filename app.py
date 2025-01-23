# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json

# --------------------------
# IMPORTS FROM YOUR MODULES
# --------------------------
from pumps.pumps import init_pumps, dose_pump  # physically spin pumps
from data.logger import log_event              # logs pump actions to hydro_events.csv
# If you have logic for thresholds, you can import it or keep config here

app = Flask(__name__)

# ---------------------------------
# 1. INIT GPIO AND PUMPS ON START
# ---------------------------------
# This ensures we set GPIO.setmode(GPIO.BCM) etc. one time.
init_pumps()

# ---------------------------------
# 2. OPTIONAL GLOBAL CONFIG
# ---------------------------------
CONFIG_FILE = "config.json"
GLOBAL_CONFIG = {
    "ph_min": 5.8,
    "ph_max": 6.2,
    "ec_min": 1.0
}

def load_config():
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            GLOBAL_CONFIG = json.load(f)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(GLOBAL_CONFIG, f)

# On startup, try loading config.json
load_config()

# ---------------------------------
# 3. INDEX ROUTE - SENSOR DATA
# ---------------------------------
@app.route("/")
def index():
    """
    Reads data/sensor_data.csv, passes rows to index.html (table, optional chart).
    If file is empty or doesn't exist, the table/chart will be empty.
    """
    sensor_rows = []
    csv_path = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")

    # If the CSV doesn't exist or is empty, we'll just have an empty list
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header row if present
            for row in reader:
                sensor_rows.append(row)

    return render_template("index.html", sensor_data=sensor_rows)

# ---------------------------------
# 4. EVENTS ROUTE - HYDRO EVENTS
# ---------------------------------
@app.route("/events")
def events():
    """
    Reads data/hydro_events.csv to show pump/dose logs.
    """
    event_rows = []
    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header
            for row in reader:
                event_rows.append(row)

    return render_template("events.html", event_data=event_rows)

# ---------------------------------
# 5. MANUAL PUMP CONTROL ROUTE
# ---------------------------------
@app.route("/manual", methods=["GET", "POST"])
def manual_control():
    """
    Form to pick a pump, run it for X seconds. 
    Calls dose_pump(...) for real, logs event to hydro_events.csv.
    """
    pump_names = ["pH_up", "pH_down", "nutrientA", "nutrientB", "nutrientC"]

    if request.method == "POST":
        selected_pump = request.form.get("pump_name")
        seconds_str = request.form.get("run_seconds")
        if selected_pump and seconds_str:
            run_sec = float(seconds_str)
            # Spin pump for real
            dose_pump(selected_pump, run_sec)
            # Log the action
            log_event("manual_dose", f"{selected_pump} for {run_sec}s")
            return redirect(url_for("manual_control"))
        else:
            # Missing input => just reload form
            return redirect(url_for("manual_control"))

    return render_template("manual.html", pump_names=pump_names)

# ---------------------------------
# 6. CONFIG ROUTE - THRESHOLDS
# ---------------------------------
@app.route("/config", methods=["GET", "POST"])
def config():
    """
    View/update pH/EC thresholds. Stored in memory or config.json.
    """
    global GLOBAL_CONFIG

    if request.method == "POST":
        # parse new values
        new_ph_min = float(request.form.get("ph_min", 5.8))
        new_ph_max = float(request.form.get("ph_max", 6.2))
        new_ec_min = float(request.form.get("ec_min", 1.0))

        GLOBAL_CONFIG["ph_min"] = new_ph_min
        GLOBAL_CONFIG["ph_max"] = new_ph_max
        GLOBAL_CONFIG["ec_min"] = new_ec_min

        # Save to config.json so it persists
        save_config()

        return redirect(url_for("config"))

    # GET => show current config
    return render_template("config.html", config=GLOBAL_CONFIG)

# ---------------------------------
# MAIN ENTRY
# ---------------------------------
if __name__ == "__main__":
    # dev server on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)

