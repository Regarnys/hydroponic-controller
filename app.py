# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json

# Pump & Logging
from pumps.pumps import init_pumps, dose_pump
from data.logger import init_event_log, init_sensor_log, log_event, log_sensor

# Sensor reading (mock or real)
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec

# (Optional) Auto dosing logic
from controller.dosing_logic import simple_ph_control, simple_ec_control

app = Flask(__name__)

# --------------------------
# 1. INIT on app startup
# --------------------------
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

# load config
load_config()

# Optionally aggregator if we want an event summary
def aggregate_event_data():
    """ Sum daily usage (seconds) by pump from hydro_events.csv """
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

            # parse "pH_up for 2s" or "Dosed pH_up for 2s"
            pump_name = None
            usage_seconds = 0.0

            if " for " in details and details.endswith("s"):
                try:
                    # e.g. "pH_up for 2s"
                    # or "pH=6.3 => Dosed pH_up for 1s"
                    idx_dosed = details.find("Dosed ")
                    if idx_dosed >= 0:
                        # skip "Dosed "
                        sub = details[idx_dosed+len("Dosed "):]
                        if " for " in sub:
                            p, sec = sub.split(" for ", 1)
                            pump_name = p.strip()
                            sec_str = sec[:-1]  # remove trailing 's'
                            usage_seconds = float(sec_str)
                    else:
                        # fallback if not "Dosed "
                        pump_part, sec_part = details.split(" for ", 1)
                        pump_name = pump_part.strip()
                        sec_str = sec_part[:-1]
                        usage_seconds = float(sec_str)
                except:
                    pass

            if not pump_name:
                # fallback if we want to parse differently or ignore
                continue

            if date_str not in aggregator:
                aggregator[date_str] = {}
            if pump_name not in aggregator[date_str]:
                aggregator[date_str][pump_name] = 0.0
            aggregator[date_str][pump_name] += usage_seconds

    return aggregator

# ------------------------------
# 2. SINGLE DASHBOARD ROUTE
# ------------------------------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    global GLOBAL_CONFIG

    # If user submitted a form
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "manual_pump":
            selected_pump = request.form.get("pump_name")
            seconds_str = request.form.get("run_seconds")
            if selected_pump and seconds_str:
                run_sec = float(seconds_str)
                dose_pump(selected_pump, run_sec)
                log_event("manual_dose", f"{selected_pump} for {run_sec}s")

        elif action == "update_config":
            new_ph_min = float(request.form.get("ph_min", 5.8))
            new_ph_max = float(request.form.get("ph_max", 6.2))
            new_ec_min = float(request.form.get("ec_min", 1.0))
            GLOBAL_CONFIG["ph_min"] = new_ph_min
            GLOBAL_CONFIG["ph_max"] = new_ph_max
            GLOBAL_CONFIG["ec_min"] = new_ec_min
            save_config()

        elif action == "auto_dosing_test":
            # e.g. run a quick sensor read + auto dose
            pH_val = read_ph()
            ec_val = read_ec()
            log_sensor("pH", pH_val)
            log_sensor("EC", ec_val)
            ph_status = simple_ph_control(pH_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
            ec_status = simple_ec_control(ec_val, GLOBAL_CONFIG["ec_min"])
            log_event("auto_ph", ph_status)
            log_event("auto_ec", ec_status)

        # after handling the POST, we fall through to re-render

    # For GET or after handling POST, gather data
    # 1) sensor_data
    sensor_rows = []
    sensor_csv = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")
    if os.path.exists(sensor_csv):
        with open(sensor_csv, "r", encoding="utf-8") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                sensor_rows.append(row)

    # 2) event_rows (recent raw logs)
    event_rows = []
    events_csv = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            r = csv.reader(f)
            next(r, None)
            for row in r:
                event_rows.append(row)

    # 3) aggregated daily usage if we want a summary
    aggregated_data = aggregate_event_data()
    all_pumps = set()
    for date_str, usage_dict in aggregated_data.items():
        for p in usage_dict.keys():
            all_pumps.add(p)
    all_pumps = sorted(all_pumps)

    # convert aggregator to a list
    summary_list = []
    for date_str in sorted(aggregated_data.keys()):
        summary_list.append({
            "date": date_str,
            "usage": aggregated_data[date_str]
        })

    # pass them all to the dashboard template
    return render_template("dashboard.html",
                           sensor_data=sensor_rows,
                           event_rows=event_rows,
                           config=GLOBAL_CONFIG,
                           all_pumps=all_pumps,
                           aggregated_data=summary_list)

# optional: remove any old routes like /manual, /config, etc.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
