# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json

# Pumps, logging, sensors, and dosing logic
from pumps.pumps import init_pumps, dose_pump
from data.logger import init_event_log, init_sensor_log, log_event, log_sensor
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec
from controller.dosing_logic import simple_ph_control, simple_ec_control

app = Flask(__name__)

# Initialization on startup
init_pumps()
init_event_log()
init_sensor_log()

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

load_config()

def aggregate_event_data():
    """
    Summarize daily usage in seconds for each pump from hydro_events.csv
    """
    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if not os.path.exists(csv_path):
        return {}

    aggregator = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) < 3: 
                continue
            timestamp_str, event_type, details = row[:3]
            date_str = timestamp_str.split(" ")[0]

            pump_name = None
            usage_seconds = 0.0
            # parse "pH_up for 2s" logic
            if " for " in details and details.endswith("s"):
                try:
                    parts = details.split(" for ")
                    pump_part = parts[0]
                    sec_part = parts[1][:-1]  # strip trailing 's'
                    pump_name = pump_part.strip()
                    usage_seconds = float(sec_part)
                except:
                    pass

            if not pump_name:
                continue

            if date_str not in aggregator:
                aggregator[date_str] = {}
            if pump_name not in aggregator[date_str]:
                aggregator[date_str][pump_name] = 0.0

            aggregator[date_str][pump_name] += usage_seconds

    return aggregator

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    global GLOBAL_CONFIG

    if request.method == "POST":
        action = request.form.get("action","")
        if action == "manual_pump":
            pump_name = request.form.get("pump_name")
            sec_str = request.form.get("run_seconds")
            if pump_name and sec_str:
                run_sec = float(sec_str)
                dose_pump(pump_name, run_sec)
                log_event("manual_dose", f"{pump_name} for {run_sec}s")

        elif action == "update_config":
            new_ph_min = float(request.form.get("ph_min", 5.8))
            new_ph_max = float(request.form.get("ph_max", 6.2))
            new_ec_min = float(request.form.get("ec_min", 1.0))
            GLOBAL_CONFIG["ph_min"] = new_ph_min
            GLOBAL_CONFIG["ph_max"] = new_ph_max
            GLOBAL_CONFIG["ec_min"] = new_ec_min
            save_config()

        elif action == "auto_dosing_test":
            pH_val = read_ph()
            ec_val = read_ec()
            log_sensor("pH", pH_val)
            log_sensor("EC", ec_val)
            ph_status = simple_ph_control(pH_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
            ec_status = simple_ec_control(ec_val, GLOBAL_CONFIG["ec_min"])
            log_event("auto_ph", ph_status)
            log_event("auto_ec", ec_status)

    # After POST or on GET, gather data for display

    # 1) sensor_data
    sensor_rows = []
    sensor_csv = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")
    if os.path.exists(sensor_csv):
        with open(sensor_csv, "r", encoding="utf-8") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                sensor_rows.append(row)

    # 2) event_rows (raw logs)
    event_rows = []
    events_csv = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                event_rows.append(row)

    # 3) aggregator summary
    aggregated_data = aggregate_event_data()
    all_pumps = set()
    for date_str, usage_dict in aggregated_data.items():
        for p in usage_dict.keys():
            all_pumps.add(p)
    all_pumps = sorted(all_pumps)

    summary_list = []
    for date_str in sorted(aggregated_data.keys()):
        summary_list.append({
            "date": date_str,
            "usage": aggregated_data[date_str]
        })

    return render_template("dashboard.html",
                           sensor_data=sensor_rows,
                           event_rows=event_rows,
                           config=GLOBAL_CONFIG,
                           all_pumps=all_pumps,
                           aggregated_data=summary_list)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
