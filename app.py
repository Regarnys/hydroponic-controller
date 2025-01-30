# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json
from datetime import datetime
import threading

# Pump, Logging, Sensor modules
from pumps.pumps import init_pumps, dose_pump
from data.logger import (init_event_log, init_sensor_log, log_event, log_sensor, start_continuous_logging)
from sensors import SensorReader
from controller.dosing_logic import simple_ph_control, simple_ec_control

app = Flask(__name__)

# Global config
CONFIG_FILE = "config.json"
GLOBAL_CONFIG = {
    "ph_min": 5.8,
    "ph_max": 6.2,
    "ec_min": 1.0,
    "pump_calibration": {}
}

def load_config():
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            loaded = json.load(f)
            GLOBAL_CONFIG.update(loaded)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(GLOBAL_CONFIG, f, indent=2)

# Aggregator for daily usage from hydro_events.csv
def aggregate_event_data():
    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if not os.path.exists(csv_path):
        return {}

    aggregator = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip
        for row in reader:
            if len(row) < 3:
                continue
            timestamp_str, event_type, details = row
            date_str = timestamp_str.split(" ")[0]

            pump_name = None
            usage_seconds = 0.0
            # parse lines like "pH_up for 2s"
            if " for " in details and details.endswith("s"):
                try:
                    parts = details.split(" for ")
                    pump_part = parts[0].strip()
                    sec_str = parts[1][:-1].strip()
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

# Utility: dose a volume in mL, using pump calibration
def dose_volume(pump_name, ml_amount):
    calibration = GLOBAL_CONFIG.get("pump_calibration", {})
    ml_per_sec = calibration.get(pump_name, 1.0)
    run_sec = ml_amount / ml_per_sec
    dose_pump(pump_name, run_sec)
    log_event("volume_dose", f"{pump_name} => {ml_amount:.2f} ml in {run_sec:.2f}s")

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    global GLOBAL_CONFIG

    message = ""  # to show status messages in the UI

    if request.method == "POST":
        action = request.form.get("action","")

        # 1) Manual Pump
        if action == "manual_pump":
            pump_name = request.form.get("pump_name","")
            sec_str = request.form.get("run_seconds","0")
            try:
                run_sec = float(sec_str)
                dose_pump(pump_name, run_sec)
                log_event("manual_dose", f"{pump_name} for {run_sec}s")
                message = f"Ran {pump_name} for {run_sec}s"
            except:
                message = "Invalid seconds input."

        # 2) Volume Dosing
        elif action == "volume_dose":
            pump_name = request.form.get("pump_name","")
            ml_str = request.form.get("ml_amount","0")
            try:
                ml_val = float(ml_str)
                dose_volume(pump_name, ml_val)
                message = f"Dosed {ml_val} ml of {pump_name}"
            except:
                message = "Invalid volume input."

        # 3) Update Config
        elif action == "update_config":
            try:
                new_ph_min = float(request.form.get("ph_min","5.8"))
                new_ph_max = float(request.form.get("ph_max","6.2"))
                new_ec_min = float(request.form.get("ec_min","1.0"))
                GLOBAL_CONFIG["ph_min"] = new_ph_min
                GLOBAL_CONFIG["ph_max"] = new_ph_max
                GLOBAL_CONFIG["ec_min"] = new_ec_min
                save_config()
                message = "Config saved."
            except:
                message = "Invalid config input."

        # 4) Auto Dosing Test
        elif action == "auto_dosing_test":
            # read sensors
            ph_val = sensor_obj.read_ph_sensor()
            ec_result = sensor_obj.read_ec_sensor()
            if ph_val is not None:
                log_sensor("pH", ph_val)
            if ec_result and ec_result.get("ec"):
                log_sensor("EC", ec_result["ec"])

            # simple logic
            ph_status = "No pH data"
            if ph_val is not None:
                ph_status = simple_ph_control(ph_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
            ec_status = "No EC data"
            if ec_result and ec_result.get("ec"):
                ec_status = simple_ec_control(ec_result["ec"], GLOBAL_CONFIG["ec_min"])
            log_event("auto_ph", ph_status)
            log_event("auto_ec", ec_status)
            message = f"Auto Dosing Test done: pH_status=({ph_status}), ec_status=({ec_status})"

        # 5) Calibrate Test Run
        elif action == "cal_test_run":
            pump_name = request.form.get("pump_name","")
            sec_str = request.form.get("cal_test_seconds","5")
            try:
                run_sec = float(sec_str)
                dose_pump(pump_name, run_sec)
                log_event("calibration_run", f"{pump_name} for {run_sec}s")
                message = f"Ran {pump_name} for {run_sec}s (measure volume!)"
            except:
                message = "Invalid input for calibration test run."

        # 6) Calibrate Save
        elif action == "cal_save":
            pump_name = request.form.get("pump_name","")
            sec_str = request.form.get("cal_test_seconds","5")
            ml_str = request.form.get("measured_ml","0")
            try:
                run_sec = float(sec_str)
                measured_ml = float(ml_str)
                ml_per_sec = measured_ml / run_sec
                GLOBAL_CONFIG["pump_calibration"][pump_name] = ml_per_sec
                save_config()
                log_event("calibration_save", f"{pump_name} => {ml_per_sec:.3f} mL/s")
                message = f"Calibration saved: {pump_name} => {ml_per_sec:.3f} mL/s"
            except:
                message = "Error saving calibration."

    # after POST or GET => gather data

    # A) pH/EC chart data
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
                ts_str, sensor_name, val_str = row
                try:
                    val_f = float(val_str)
                except:
                    continue
                if sensor_name == "pH":
                    ph_data.append([ts_str, val_f])
                elif sensor_name == "EC":
                    ec_data.append([ts_str, val_f])
    ph_data = ph_data[-20:]
    ec_data = ec_data[-20:]

    # B) Events for the "Events" tab
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
            r = csv.reader(f)
            header = next(r, None)
            for row in r:
                if len(row) >= 3:
                    event_rows_all.append(row)
    def parse_ts(ts):
        from datetime import datetime
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.min
    event_rows_all.sort(key=lambda x: parse_ts(x[0]), reverse=True)
    total_events = len(event_rows_all)
    start_i = (page-1)*page_size
    end_i = start_i+page_size
    event_rows = event_rows_all[start_i:end_i]
    has_next_page = end_i < total_events
    has_prev_page = page>1

    # C) aggregator usage
    aggregated_data = aggregate_event_data()
    all_pumps = set()
    for date_str, usage_map in aggregated_data.items():
        for p in usage_map.keys():
            all_pumps.add(p)
    all_pumps = sorted(all_pumps)

    summary_list = []
    for date_str in sorted(aggregated_data.keys()):
        summary_list.append({"date": date_str, "usage": aggregated_data[date_str]})

    return render_template("dashboard.html",
        message=message,
        ph_data=ph_data,
        ec_data=ec_data,
        event_rows=event_rows,
        current_page=page,
        has_next_page=has_next_page,
        has_prev_page=has_prev_page,
        total_events=total_events,
        all_pumps=all_pumps,
        summary_list=summary_list,
        config=GLOBAL_CONFIG
    )

@app.route("/")
def index():
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    # init
    init_pumps()
    init_event_log()
    init_sensor_log()
    load_config()

    # sensor
    sensor_obj = SensorReader(i2c_bus=1, ph_address=0x63, ec_address=0x64)

    # background logging
    def run_logger():
        start_continuous_logging(sensor_obj, interval=10)
    t = threading.Thread(target=run_logger, daemon=True)
    t.start()

    app.run(host="0.0.0.0", port=5001, debug=True)
