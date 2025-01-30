# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json
from datetime import datetime
import threading

# Pump, Logging, and Sensor modules
from pumps.pumps import init_pumps, dose_pump
from data.logger import init_event_log, init_sensor_log, log_event, log_sensor, start_continuous_logging
from sensors_pkg.sensors import SensorReader
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
    Returns dict: { 'YYYY-MM-DD': {'pH_up':4.0, 'pH_down':2.0, ...}, ... }
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

            # parse lines like "pH_up for 2s"
            if " for " in details and details.endswith("s"):
                try:
                    parts = details.split(" for ")
                    pump_part = parts[0].strip()
                    sec_str = parts[1][:-1].strip()  # remove 's' at end
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
            # Example: read sensor, log data, but no auto-dosing triggers
            from sensors.ph_sensor import read_ph
            from sensors.ec_sensor import read_ec

            pH_val = read_ph()
            if pH_val is not None:
                log_sensor("pH", pH_val)

            ec_val = read_ec()
            if ec_val is not None:
                log_sensor("EC", ec_val)

            log_event("auto_test", "Sensors read, no auto-dosing performed")

    # For GET or after POST, gather data for the charts

    # Step A) read from sensor_data.csv for pH, EC arrays
    ph_data = []
    ec_data = []
    sensor_csv = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")
    if os.path.exists(sensor_csv):
        with open(sensor_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                ts_str, sensor_name, val_str = row[:3]
                try:
                    val_f = float(val_str)
                except ValueError:
                    continue

                if sensor_name == "pH":
                    ph_data.append([ts_str, val_f])
                elif sensor_name == "EC":
                    ec_data.append([ts_str, val_f])

    # Sort or limit data as needed
    ph_data = ph_data[-20:]
    ec_data = ec_data[-20:]

    # Step B) event logs w/ pagination
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

    # Step C) aggregator summary
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

    return render_template(
        "dashboard.html",
        config=GLOBAL_CONFIG,
        ph_data=ph_data,
        ec_data=ec_data,
        event_rows=event_rows,
        current_page=page,
        has_next_page=has_next_page,
        has_prev_page=has_prev_page,
        total_events=total_events,
        all_pumps=all_pumps,
        aggregated_data=summary_list
    )

if __name__ == "__main__":
    # 1) Create a sensor for the background logger
    sensor_obj = SensorReader(i2c_bus=1, ph_address=0x63, ec_address=0x64)

    # 2) Launch continuous logging in a background thread
    #    so it doesn't block Flask from running.
    logging_interval = 10  # seconds
    def run_logger():
        from data.logger import start_continuous_logging
        start_continuous_logging(sensor_obj, interval=logging_interval)

    t = threading.Thread(target=run_logger, daemon=True)
    t.start()

    # 3) Run the Flask server
    app.run(host="0.0.0.0", port=5001, debug=True)

