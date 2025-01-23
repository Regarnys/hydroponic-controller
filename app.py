# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json

# GPIO and Pump system
from pumps.pumps import init_pumps, dose_pump

# Logging
from data.logger import init_event_log, init_sensor_log, log_event, log_sensor

# Optional sensor modules (mock or real)
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec

# Optional naive dosing logic
from controller.dosing_logic import simple_ph_control, simple_ec_control

app = Flask(__name__)

# 1. Initialize pump pins & logs
init_pumps()
init_event_log()
init_sensor_log()

# 2. Global config stored in config.json
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

# load config on startup
load_config()

@app.route("/")
def index():
    """
    Displays sensor_data.csv in a table, plus a Chart.js chart for pH if desired.
    """
    sensor_rows = []
    csv_path = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None) # skip header
            for row in reader:
                sensor_rows.append(row)

    return render_template("index.html", sensor_data=sensor_rows)

@app.route("/events")
def events():
    """
    Show hydro_events.csv logs.
    """
    event_rows = []
    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                event_rows.append(row)

    return render_template("events.html", event_data=event_rows)

@app.route("/manual", methods=["GET", "POST"])
def manual_control():
    """
    Form to manually run a pump for X seconds.
    """
    pump_names = ["pH_up", "pH_down", "nutrientA", "nutrientB", "nutrientC"]

    if request.method == "POST":
        selected_pump = request.form.get("pump_name")
        seconds_str = request.form.get("run_seconds")

        if selected_pump and seconds_str:
            run_sec = float(seconds_str)
            dose_pump(selected_pump, run_sec)
            log_event("manual_dose", f"{selected_pump} for {run_sec}s")
            return redirect(url_for("manual_control"))
        else:
            return redirect(url_for("manual_control"))

    return render_template("manual.html", pump_names=pump_names)

@app.route("/config", methods=["GET", "POST"])
def config():
    global GLOBAL_CONFIG

    if request.method == "POST":
        new_ph_min = float(request.form.get("ph_min", 5.8))
        new_ph_max = float(request.form.get("ph_max", 6.2))
        new_ec_min = float(request.form.get("ec_min", 1.0))

        GLOBAL_CONFIG["ph_min"] = new_ph_min
        GLOBAL_CONFIG["ph_max"] = new_ph_max
        GLOBAL_CONFIG["ec_min"] = new_ec_min
        save_config()

        return redirect(url_for("config"))

    return render_template("config.html", config=GLOBAL_CONFIG)

@app.route("/auto_dosing_test")
def auto_dosing_test():
    """
    Example route that reads mock sensor, applies naive auto logic,
    logs result, and returns a simple message.
    """
    pH_val = read_ph()
    ec_val = read_ec()
    log_sensor("pH", pH_val)
    log_sensor("EC", ec_val)

    # Use config thresholds
    ph_status = simple_ph_control(pH_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
    ec_status = simple_ec_control(ec_val, GLOBAL_CONFIG["ec_min"])

    # if "Dosed" in ph_status: log_event("auto_ph", ph_status)
    # if "Dosed" in ec_status: log_event("auto_ec", ec_status)
    # or log them always:
    log_event("auto_ph", ph_status)
    log_event("auto_ec", ec_status)

    return f"Ran auto dosing. pH={pH_val}, ec={ec_val}. <br> {ph_status} <br> {ec_status}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
