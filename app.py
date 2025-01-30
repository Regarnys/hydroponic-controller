# File: app.py

from flask import Flask, render_template, request, redirect, url_for
import csv
import os
import json
from datetime import datetime
import threading

# Pump, Logging, Sensor
from pumps.pumps import init_pumps, dose_pump
from data.logger import (init_event_log, init_sensor_log,
                         log_event, log_sensor, start_continuous_logging)
from sensors import SensorReader
# Optional auto dosing
from controller.dosing_logic import simple_ph_control, simple_ec_control

app = Flask(__name__)

CONFIG_FILE = "config.json"
GLOBAL_CONFIG = {
    "ph_min": 5.8,
    "ph_max": 6.2,
    "ec_min": 1.0,
    "pump_calibration": {}  # For volume-based dosing => "pH_up": ml_per_sec, etc.
}

def load_config():
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            loaded = json.load(f)
            # Merge loaded into GLOBAL_CONFIG
            GLOBAL_CONFIG.update(loaded)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(GLOBAL_CONFIG, f, indent=2)

@app.before_first_request
def init_system():
    # Called once when the first request arrives
    init_pumps()
    init_event_log()
    init_sensor_log()
    load_config()

#-------------------------------
# Aggregator for hydro_events
#-------------------------------
def aggregate_event_data():
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
            timestamp_str, event_type, details = row
            date_str = timestamp_str.split(" ")[0]

            # parse usage if lines like "pH_up for 2s"
            pump_name = None
            usage_seconds = 0.0
            if " for " in details and details.endswith("s"):
                try:
                    parts = details.split(" for ")
                    pump_part = parts[0].strip()
                    sec_str = parts[1][:-1].strip()  # remove 's'
                    usage_seconds = float(sec_str)
                    pump_name = pump_part
                except:
                    pass

            if not pump_name:
                # skip lines that don't match usage
                continue

            if date_str not in aggregator:
                aggregator[date_str] = {}
            if pump_name not in aggregator[date_str]:
                aggregator[date_str][pump_name] = 0.0
            aggregator[date_str][pump_name] += usage_seconds

    return aggregator

#-------------------------------
# Utility: dose volume
#-------------------------------
def dose_volume(pump_name, ml_amount):
    calibration = GLOBAL_CONFIG.get("pump_calibration", {})
    ml_per_sec = calibration.get(pump_name, 1.0)
    run_sec = ml_amount / ml_per_sec
    dose_pump(pump_name, run_sec)
    log_event("volume_dose", f"{pump_name} => {ml_amount:.2f} ml in {run_sec:.2f}s")

#-------------------------------
# MAIN ROUTE: let's call it /dashboard
#-------------------------------
@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    global GLOBAL_CONFIG
    if request.method == "POST":
        action = request.form.get("action","")

        if action == "manual_pump":
            pump_name = request.form.get("pump_name")
            sec_str = request.form.get("run_seconds","0")
            try:
                run_sec = float(sec_str)
                dose_pump(pump_name, run_sec)
                log_event("manual_dose", f"{pump_name} for {run_sec}s")
            except:
                pass

        elif action == "update_config":
            new_ph_min = float(request.form.get("ph_min","5.8"))
            new_ph_max = float(request.form.get("ph_max","6.2"))
            new_ec_min = float(request.form.get("ec_min","1.0"))
            GLOBAL_CONFIG["ph_min"] = new_ph_min
            GLOBAL_CONFIG["ph_max"] = new_ph_max
            GLOBAL_CONFIG["ec_min"] = new_ec_min
            save_config()

        elif action == "auto_dosing_test":
            # example read & log
            pH_val = sensor_obj.read_ph_sensor()
            ec_dict = sensor_obj.read_ec_sensor()
            if pH_val is not None:
                log_sensor("pH", pH_val)
            if ec_dict and ec_dict.get("ec") is not None:
                log_sensor("EC", ec_dict["ec"])

            # run naive logic
            ph_status = simple_ph_control(pH_val, GLOBAL_CONFIG["ph_min"], GLOBAL_CONFIG["ph_max"])
            ec_status = "No ec data"
            if ec_dict and ec_dict.get("ec"):
                ec_status = simple_ec_control(ec_dict["ec"], GLOBAL_CONFIG["ec_min"])
            log_event("auto_ph", ph_status)
            log_event("auto_ec", ec_status)

        elif action == "volume_dose":
            pump_name = request.form.get("pump_name")
            ml_str = request.form.get("ml_amount","0")
            try:
                ml_val = float(ml_str)
                dose_volume(pump_name, ml_val)
            except:
                pass

    # build chart data from sensor_data.csv
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

    # events tab
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
    # sort desc
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
    has_next_page = end_i < total_events
    has_prev_page = page > 1

    # aggregator summary
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
        aggregated_data=summary_list
    )


# separate calibrate route
@app.route("/calibrate", methods=["GET","POST"])
def calibrate_pump():
    global GLOBAL_CONFIG
    pump_names = ["pH_up","pH_down","nutrientA","nutrientB","nutrientC"]
    message = ""

    if request.method == "POST":
        action = request.form.get("action","")
        pump = request.form.get("pump_name","")
        if action == "test_run":
            sec_str = request.form.get("test_run_seconds","5")
            try:
                run_sec = float(sec_str)
                dose_pump(pump, run_sec)
                log_event("calibration_run", f"{pump} for {run_sec}s")
                message = f"Ran {pump} for {run_sec:.2f}s. Measure the volume dispensed!"
            except:
                message = "Invalid seconds value."

        elif action == "save_measurement":
            sec_str = request.form.get("test_run_seconds","5")
            ml_str = request.form.get("measured_ml","0")
            try:
                run_sec = float(sec_str)
                measured_ml = float(ml_str)
                if run_sec>0:
                    ml_per_sec = measured_ml / run_sec
                    if "pump_calibration" not in GLOBAL_CONFIG:
                        GLOBAL_CONFIG["pump_calibration"]={}
                    GLOBAL_CONFIG["pump_calibration"][pump] = ml_per_sec
                    save_config()
                    log_event("calibration_save", f"{pump} => {ml_per_sec:.3f} mL/s")
                    message = f"Calibration saved: {pump} => {ml_per_sec:.3f} mL/s"
                else:
                    message = "Seconds must be > 0"
            except:
                message = "Invalid input"

    return render_template("calibrate.html",
                           pump_names=pump_names,
                           config=GLOBAL_CONFIG,
                           message=message)

@app.route("/config", methods=["GET", "POST"])
def config():
    global GLOBAL_CONFIG
    if request.method=="POST":
        new_ph_min = float(request.form.get("ph_min", 5.8))
        new_ph_max = float(request.form.get("ph_max", 6.2))
        new_ec_min = float(request.form.get("ec_min", 1.0))
        GLOBAL_CONFIG["ph_min"] = new_ph_min
        GLOBAL_CONFIG["ph_max"] = new_ph_max
        GLOBAL_CONFIG["ec_min"] = new_ec_min
        save_config()
        return redirect(url_for("config"))

    return render_template("config.html", config=GLOBAL_CONFIG)

@app.route("/")
def index():
    # simple home redirect
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    # 1) init pumps, logs, config
    init_pumps()
    init_event_log()
    init_sensor_log()
    load_config()

    # 2) create sensor for continuous logging
    sensor_obj = SensorReader(i2c_bus=1, ph_address=0x63, ec_address=0x64)

    # 3) Start a background thread for continuous logging
    logging_interval = 10
    import threading
    def run_logger():
        start_continuous_logging(sensor_obj, interval=logging_interval)
    t = threading.Thread(target=run_logger, daemon=True)
    t.start()

    # 4) run the Flask server on port 5001
    app.run(host="0.0.0.0", port=5001, debug=True)


