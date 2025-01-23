# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json
from datetime import datetime

# Pump, Logging, Sensor modules
from pumps.pumps import init_pumps, dose_pump
from data.logger import init_event_log, init_sensor_log, log_event, log_sensor
from sensors.ph_sensor import read_ph
from sensors.ec_sensor import read_ec

# Optional auto dosing logic
from controller.dosing_logic import simple_ph_control, simple_ec_control

app = Flask(__name__)

# ---------------------------
# 1. Initialization on startup
# ---------------------------
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

# Load config at startup
load_config()

# ---------------------------
# 2. Aggregator for daily usage
# ---------------------------
def aggregate_event_data():
    """
    Reads hydro_events.csv, aggregates daily usage in seconds per pump.
    Returns dict: { '2025-04-10': {'pH_up':4.0, 'pH_down':2.0, ...}, ... }
    """
    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if not os.path.exists(csv_path):
        return {}

    aggregator = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip: timestamp,event,details
        for row in reader:
            if len(row) < 3:
                continue
            timestamp_str, event_type, details = row[:3]
            date_str = timestamp_str.split(" ")[0]

            pump_name = None
            usage_seconds = 0.0

            # parse "pH_up for 2s" or similar
            if " for " in details and details.endswith("s"):
                try:
                    parts = details.split(" for ")
                    pump_part = parts[0].strip()      # e.g. "pH_up"
                    sec_str = parts[1][:-1].strip()   # remove 's'
                    usage_seconds = float(sec_str)
                    pump_name = pump_part
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

# ---------------------------
# 3. Single /dashboard route
# ---------------------------
@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    global GLOBAL_CONFIG

    # 3.1 Handle POST form actions
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
            new_ph_min = float(request.form.get("ph_min", "5.8"))
            new_ph_max = float(request.form.get("ph_max", "6.2"))
            new_ec_min = float(request.form.get("ec_min", "1.0"))
            GLOBAL_CONFIG["ph_min"] = new_ph_min
            GLOBAL_CONFIG["ph_max"] = new_ph_max
            GLOBAL_CONFIG["ec_min"] = new_ec_min
            save_config()
        elif action == "auto_dosing_test":
            # e.g. read sensors, do naive auto logic
            pH_val = read_ph()
            ec_val = read_ec()
            log_sensor("pH", pH_val)
            log_sensor("EC", ec_val)
            ph_status = simple_ph_control(pH_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
            ec_status = simple_ec_control(ec_val, GLOBAL_CONFIG["ec_min"])
            log_event("auto_ph", ph_status)
            log_event("auto_ec", ec_status)

    # 3.2 For GET or after POST, gather data

    # A) pH & EC data for the charts
    ph_data = []
    ec_data = []
    sensor_csv = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")
    if os.path.exists(sensor_csv):
        with open(sensor_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                # row: [timestamp, sensor_name, value]
                if len(row) < 3:
                    continue
                ts_str, sensor_name, val_str = row[:3]
                try:
                    val_f = float(val_str)
                except ValueError:
                    continue
                if sensor_name == "pH":
                    ph_data.append((ts_str, val_f))
                elif sensor_name == "EC":
                    ec_data.append((ts_str, val_f))

    # sort them by timestamp if needed, or just keep order
    # let's keep them in ascending time if they are in the file that way
    # limit to last 20 for each
    ph_data = ph_data[-20:]
    ec_data = ec_data[-20:]

    # B) Events - sorted desc, 25 per page
    page_str = request.args.get("page","1")
    try:
        page = int(page_str)
    except:
        page = 1
    page_size = 25
    event_rows_all = []
    events_csv = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) >= 3:
                    event_rows_all.append(row)
    # sort descending by timestamp
    def parse_ts(ts):
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.min
    event_rows_all.sort(key=lambda x: parse_ts(x[0]), reverse=True)

    total_events = len(event_rows_all)
    start_i = (page-1)*page_size
    end_i = start_i + page_size
    event_rows = event_rows_all[start_i:end_i]
    has_next_page = (end_i < total_events)
    has_prev_page = (page > 1)

    # C) aggregator summary
    aggregated_data = aggregate_event_data()
    all_pumps = set()
    for date_str, usage_map in aggregated_data.items():
        for p in usage_map.keys():
            all_pumps.add(p)
    all_pumps = sorted(all_pumps)

    summary_list = []
    for date_str in sorted(aggregated_data.keys()):
        summary_list.append({
            "date": date_str,
            "usage": aggregated_data[date_str]
        })

    # 3.3 Render the single dashboard page
    return render_template("dashboard.html",
                           config=GLOBAL_CONFIG,
                           ph_data=ph_data,
                           ec_data=ec_data,
                           event_rows=event_rows,
                           current_page=page,
                           has_next_page=has_next_page,
                           has_prev_page=has_prev_page,
                           total_events=total_events,
                           all_pumps=all_pumps,
                           aggregated_data=summary_list)

if __name__ == "__main__":
    # run the server
    app.run(host="0.0.0.0", port=5000, debug=True)
