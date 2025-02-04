# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json
from datetime import datetime
import threading

# Pump, Logging, and Sensor modules
from pumps.pumps import init_pumps, dose_pump
from data.logger import (
    init_event_log,
    init_sensor_log,
    log_event,
    log_sensor,
    start_continuous_logging
)
from sensors import SensorReader  # Uses the updated AtlasI2C-based code
from controller.dosing_logic import simple_ph_control, simple_ec_control

app = Flask(__name__)

# Global config (thresholds + pump_calibration)
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

# ---------------------------
# Aggregators
# ---------------------------

def aggregate_event_data():
    """
    Reads hydro_events.csv, aggregates daily usage in seconds per pump.
    Returns dict: { 'YYYY-MM-DD': {'pH_up': 4.0, 'nutrientA': 2.0, ...}, ... }
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
            # Only unpack the first three columns even if more exist
            timestamp_str, event_type, details = row[:3]
            date_str = timestamp_str.split(" ")[0]

            pump_name = None
            usage_seconds = 0.0

            if " for " in details and details.endswith("s"):
                try:
                    parts = details.split(" for ")
                    pump_part = parts[0].strip()
                    sec_str = parts[1][:-1].strip()  # remove trailing 's'
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


def aggregate_sensor_data_for_today():
    """
    Return pH_min/pH_max for today's date from sensor_data.csv.
    You can extend for EC stats too if you want.
    """
    from datetime import datetime
    today_str = datetime.now().strftime("%Y-%m-%d")
    csv_path = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")
    pH_values = []

    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                ts_str, sensor_name, val_str = row
                date_only = ts_str.split(" ")[0]
                if date_only == today_str and sensor_name == "pH":
                    try:
                        val_f = float(val_str)
                        pH_values.append(val_f)
                    except:
                        pass

    if pH_values:
        return {
            "pH_min": min(pH_values),
            "pH_max": max(pH_values)
        }
    else:
        return {
            "pH_min": None,
            "pH_max": None
        }

def build_usage_bar_data(event_aggregator, all_pumps):
    """
    Create a list of { date:'YYYY-MM-DD', pH_up: X, pH_down: Y, ... }
    for each date in aggregator.
    Used for the stacked bar chart in 'Insights'.
    """
    usage_bar_data = []
    sorted_dates = sorted(event_aggregator.keys())
    for date_str in sorted_dates:
        rowdict = {"date": date_str}
        for pump in all_pumps:
            rowdict[pump] = event_aggregator[date_str].get(pump, 0)
        usage_bar_data.append(rowdict)
    return usage_bar_data

def get_recent_interesting_events():
    """
    Return last 5 'interesting' events (like calibrations, errors, auto dosing).
    This is just an example filter. Adjust as you wish.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if not os.path.exists(csv_path):
        return []

    all_events = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 3:
                all_events.append(row)

    def parse_ts(ts):
        try:
            return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        except:
            return datetime.min

    all_events.sort(key=lambda x: parse_ts(x[0]), reverse=True)

    # filter
    interesting = []
    for ev in all_events:
        ts, etype, details = ev
        if ('calibration' in etype.lower()) or ('error' in etype.lower()) or ('auto' in etype.lower()):
            interesting.append(ev)
    return interesting[:5]

# Utility to dose volume in mL
def dose_volume(pump_name, ml_amount):
    calibration = GLOBAL_CONFIG.get("pump_calibration", {})
    ml_per_sec = calibration.get(pump_name, 1.0)
    run_sec = ml_amount / ml_per_sec
    dose_pump(pump_name, run_sec)
    log_event("volume_dose", f"{pump_name} => {ml_amount:.2f} ml in {run_sec:.2f}s")

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    global GLOBAL_CONFIG
    message = ""

    if request.method == "POST":
        action = request.form.get("action","")

        if action == "manual_pump":
            pump_name = request.form.get("pump_name","")
            sec_str = request.form.get("run_seconds","0")
            try:
                run_sec = float(sec_str)
                dose_pump(pump_name, run_sec)
                log_event("manual_dose", f"{pump_name} for {run_sec}s")
                message = f"Ran {pump_name} for {run_sec}s"
            except:
                message = "Invalid input for manual pump."

        elif action == "volume_dose":
            pump_name = request.form.get("pump_name","")
            ml_str = request.form.get("ml_amount","0")
            try:
                ml_val = float(ml_str)
                dose_volume(pump_name, ml_val)
                message = f"Dosed {ml_val} ml of {pump_name}"
            except:
                message = "Invalid volume input."

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

        elif action == "auto_dosing_test":
            # read sensors
            ph_val = sensor_obj.read_ph_sensor()
            ec_result = sensor_obj.read_ec_sensor()
            if ph_val is not None:
                log_sensor("pH", ph_val)
            if ec_result and ec_result.get("ec"):
                log_sensor("EC", ec_result["ec"])

            # run naive logic
            ph_status = "No pH data"
            if ph_val is not None:
                ph_status = simple_ph_control(ph_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
            ec_status = "No EC data"
            if ec_result and ec_result.get("ec"):
                ec_status = simple_ec_control(ec_result["ec"], GLOBAL_CONFIG["ec_min"])

            log_event("auto_ph", ph_status)
            log_event("auto_ec", ec_status)
            message = f"Auto Dosing Test done: pH=({ph_status}), ec=({ec_status})"

        # Calibration actions
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

    # ========== GATHER DATA FOR TABS ==========

    # A) Live Data (pH/EC charts)
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
                except ValueError:
                    continue
                if sensor_name == "pH":
                    ph_data.append([ts_str, val_f])
                elif sensor_name == "EC":
                    ec_data.append([ts_str, val_f])
    # Show only last 20 readings (example)
    ph_data = ph_data[-20:]
    ec_data = ec_data[-20:]

    # B) aggregator for events usage
    event_aggregator = aggregate_event_data()
    all_pumps = set()
    for date_str, usage_map in event_aggregator.items():
        for p in usage_map.keys():
            all_pumps.add(p)
    all_pumps = sorted(all_pumps)

    # build stacked bar usage data
    usage_bar_data = build_usage_bar_data(event_aggregator, all_pumps)

    # simple daily usage for today's date
    today_str = datetime.now().strftime("%Y-%m-%d")
    daily_pump_usage = 0
    if today_str in event_aggregator:
        daily_pump_usage = sum(event_aggregator[today_str].values())

    # daily pH min/max
    sensor_today = aggregate_sensor_data_for_today()
    daily_pH_min = sensor_today["pH_min"]
    daily_pH_max = sensor_today["pH_max"]

    # interesting events
    interesting_events = get_recent_interesting_events()

    # C) EVENTS TAB with pagination
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
            rr = csv.reader(f)
            header = next(rr, None)
            for row in rr:
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

    # D) usage aggregator summary (like old "Usage" tab)
    summary_list = []
    for date_str in sorted(event_aggregator.keys()):
        summary_list.append({
            "date": date_str,
            "usage": event_aggregator[date_str]
        })

    return render_template(
        "dashboard.html",
        message=message,
        # For Live Data
        ph_data=ph_data,
        ec_data=ec_data,
        # For aggregator summary usage tab
        summary_list=summary_list,
        # For events tab
        event_rows=event_rows,
        current_page=page,
        has_next_page=has_next_page,
        has_prev_page=has_prev_page,
        total_events=total_events,
        # For config
        config=GLOBAL_CONFIG,
        # For Insights
        daily_pH_min=daily_pH_min,
        daily_pH_max=daily_pH_max,
        daily_pump_usage=daily_pump_usage,
        usage_bar_data=usage_bar_data,
        interesting_events=interesting_events,
        all_pumps=list(all_pumps)
    )

@app.route("/")
def index():
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    # 1) init
    init_pumps()
    init_event_log()
    init_sensor_log()
    load_config()

    # 2) create sensor for continuous logging
    #    Must match the new SensorReader's init signature with i2c_bus,
    #    ph_address, and ec_address.
    sensor_obj = SensorReader(i2c_bus=1, ph_address=0x63, ec_address=0x64)

    # 3) background logging
    def run_logger():
        start_continuous_logging(sensor_obj, interval=10)
    t = threading.Thread(target=run_logger, daemon=True)
    t.start()

    # 4) run the Flask server
    app.run(host="0.0.0.0", port=5001, debug=True)



