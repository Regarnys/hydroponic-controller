# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json

# GPIO and Pump system
from pumps.pumps import init_pumps, dose_pump

# Logging
from data.logger import init_event_log, init_sensor_log, log_event, log_sensor

# Mock or real sensor modules
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec

# Optional auto dosing logic
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

# Load config on startup
load_config()

@app.route("/")
def index():
    """
    Displays sensor_data.csv in a table and can optionally chart pH with Chart.js.
    """
    sensor_rows = []
    csv_path = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                sensor_rows.append(row)

    return render_template("index.html", sensor_data=sensor_rows)

@app.route("/events")
def events():
    """
    Show hydro_events.csv logs (raw listing).
    """
    event_rows = []
    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
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
    logs result, and returns a message with the results.
    """
    pH_val = read_ph()
    ec_val = read_ec()
    log_sensor("pH", pH_val)
    log_sensor("EC", ec_val)

    ph_status = simple_ph_control(pH_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
    ec_status = simple_ec_control(ec_val, GLOBAL_CONFIG["ec_min"])

    # Always log
    log_event("auto_ph", ph_status)
    log_event("auto_ec", ec_status)

    return f"Ran auto dosing. pH={pH_val}, ec={ec_val}. <br> {ph_status} <br> {ec_status}"

# -------------------------------------------------------------
# NEW: AGGREGATION FOR EVENTS SUMMARY
# -------------------------------------------------------------
def aggregate_event_data():
    """
    Reads hydro_events.csv, aggregates daily usage in seconds per pump.
    We'll parse lines like:
      timestamp, event_type, details
      "2025-04-10 14:05:00,manual_dose,pH_up for 2s"
    If row has more than 3 columns, we slice the first three.
    If row has fewer, we skip it.
    """

    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if not os.path.exists(csv_path):
        return {}

    aggregator = {}  # {date_str: {pump_name: total_seconds}}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip "timestamp,event,details"

        for row in reader:
            # if row has fewer than 3 fields, skip
            if len(row) < 3:
                continue
            # if row has extra columns, take only first 3
            timestamp_str, event_type, details = row[:3]

            # Extract date from timestamp e.g. "2025-04-10"
            date_str = timestamp_str.split(" ")[0]

            # parse "pH_up for 2s" => pump_name = "pH_up", usage_seconds=2.0
            pump_name = None
            usage_seconds = 0.0

            parts = details.split()
            # e.g. ["pH_up", "for", "2s"]
            if len(parts) == 3 and parts[1] == "for" and parts[2].endswith("s"):
                pump_name = parts[0]
                sec_str = parts[2].replace("s","")
                try:
                    usage_seconds = float(sec_str)
                except ValueError:
                    usage_seconds = 1.0
            else:
                # fallback: treat entire details as pump_name, usage=1.0
                pump_name = details
                usage_seconds = 1.0

            # aggregator
            if date_str not in aggregator:
                aggregator[date_str] = {}
            if pump_name not in aggregator[date_str]:
                aggregator[date_str][pump_name] = 0.0

            aggregator[date_str][pump_name] += usage_seconds

    return aggregator

@app.route("/events_summary")
def events_summary():
    """
    Show a daily breakdown of total usage (seconds) per pump as a table or chart.
    """
    data_by_date = aggregate_event_data()

    # gather all pumps across all dates
    all_pumps = set()
    for date_str, usage_dict in data_by_date.items():
        for p in usage_dict.keys():
            all_pumps.add(p)
    all_pumps = sorted(all_pumps)

    # Convert aggregator dict to a list so we can easily loop in Jinja
    # e.g. [ {date: "2025-04-10", usage: {"pH_up":4, "nutrientA":2}}, ... ]
    aggregated_list = []
    for date_str in sorted(data_by_date.keys()):
        aggregated_list.append({
            "date": date_str,
            "usage": data_by_date[date_str]
        })

    return render_template("events_summary.html",
                           all_pumps=all_pumps,
                           aggregated_data=aggregated_list)

# -------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
