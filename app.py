# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json

# Import your real pump function to physically spin the pumps
from pumps.pumps import dose_pump

# Import logging methods, if desired
from data.logger import log_event

# If you have a separate config or dosing logic, you can import that:
# from controller.dosing_logic import simple_ph_control, simple_ec_control
# But here we might keep a small config in this file for demonstration

app = Flask(__name__)

# -------------------------------
#  1. OPTIONAL: LOAD A CONFIG
# -------------------------------
CONFIG_FILE = "config.json"
GLOBAL_CONFIG = {
    "ph_min": 5.8,
    "ph_max": 6.2,
    "ec_min": 1.0
}

def load_config():
    """Load config from config.json if exists."""
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            GLOBAL_CONFIG = json.load(f)

def save_config():
    """Save GLOBAL_CONFIG to config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(GLOBAL_CONFIG, f)

# At startup, load if config.json is present
load_config()


# -------------------------------
#  2. INDEX ROUTE - SENSOR DATA
# -------------------------------
@app.route("/")
def index():
    """
    Reads sensor_data.csv, displays in a table, and optionally pass data for charts.
    """
    sensor_rows = []
    csv_path = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")
    
    # Safely handle if file doesn't exist
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header
            for row in reader:
                sensor_rows.append(row)
    else:
        # if there's no sensor_data.csv yet, keep sensor_rows empty
        pass

    # Pass sensor_rows to the template
    return render_template("index.html", sensor_data=sensor_rows)


# -------------------------------
#  3. EVENTS ROUTE - PUMP/DOSE LOGS
# -------------------------------
@app.route("/events")
def events():
    """
    Reads hydro_events.csv and displays pump/dosing logs.
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


# -------------------------------
#  4. MANUAL PUMP CONTROL
# -------------------------------
@app.route("/manual", methods=["GET", "POST"])
def manual_control():
    """
    A route to manually run a pump for X seconds.
    """
    pump_names = ["pH_up", "pH_down", "nutrientA", "nutrientB", "nutrientC"]

    if request.method == "POST":
        selected_pump = request.form.get("pump_name")
        seconds_str = request.form.get("run_seconds")

        if selected_pump and seconds_str:
            run_sec = float(seconds_str)

            # Physically spin the pump
            dose_pump(selected_pump, run_sec)

            # Log the event
            log_event("manual_dose", f"{selected_pump} for {run_sec}s")

            return redirect(url_for("manual_control"))
        else:
            # missing fields => just reload
            return redirect(url_for("manual_control"))

    # GET => display the form
    return render_template("manual.html", pump_names=pump_names)


# -------------------------------
#  5. CONFIG ROUTE - THRESHOLDS
# -------------------------------
@app.route("/config", methods=["GET", "POST"])
def config():
    """
    View or update the pH/EC thresholds stored in GLOBAL_CONFIG.
    Optionally persist them in config.json.
    """
    global GLOBAL_CONFIG

    if request.method == "POST":
        # parse new values from the form
        new_ph_min = float(request.form.get("ph_min", 5.8))
        new_ph_max = float(request.form.get("ph_max", 6.2))
        new_ec_min = float(request.form.get("ec_min", 1.0))

        GLOBAL_CONFIG["ph_min"] = new_ph_min
        GLOBAL_CONFIG["ph_max"] = new_ph_max
        GLOBAL_CONFIG["ec_min"] = new_ec_min

        # Save to config.json so it persists
        save_config()

        return redirect(url_for("config"))

    # GET => show current config values
    return render_template("config.html", config=GLOBAL_CONFIG)


# -------------------------------
#  MAIN ENTRY POINT
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

