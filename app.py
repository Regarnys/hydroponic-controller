# File: app.py

from flask import Flask, render_template, request, redirect, url_for, Response, send_from_directory
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
from sensors import SensorReader
from controller.dosing_logic import simple_ph_control, simple_ec_control
from camera.camera import PlantCamera, generate_frames

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

# --- Aggregation Functions ---

def aggregate_event_data():
    """Aggregate event data from hydro_events.csv.
       Returns a dictionary mapping dates (YYYY-MM-DD) to a dictionary of pump usage.
       Expected CSV columns: timestamp, pump, usage_amount, ...
    """
    events_csv = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    aggregator = {}
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # Skip header if present
            for row in reader:
                if len(row) < 3:
                    continue
                ts_str, pump, usage_str = row[:3]
                try:
                    usage = float(usage_str)
                except ValueError:
                    continue
                try:
                    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    continue
                if date_str not in aggregator:
                    aggregator[date_str] = {}
                if pump not in aggregator[date_str]:
                    aggregator[date_str][pump] = 0
                aggregator[date_str][pump] += usage
    return aggregator

def aggregate_sensor_data_for_today():
    """Aggregate sensor data for today's readings from sensor_data.csv.
       Returns a dictionary with daily minimum and maximum pH values.
       Expected CSV columns: timestamp, sensor_name, value, ...
    """
    sensor_csv = os.path.join(os.path.dirname(__file__), "data", "sensor_data.csv")
    today = datetime.now().strftime("%Y-%m-%d")
    ph_values = []
    if os.path.exists(sensor_csv):
        with open(sensor_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                ts_str, sensor_name, val_str = row[:3]
                try:
                    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
                if dt.strftime("%Y-%m-%d") == today and sensor_name == "pH":
                    try:
                        ph_value = float(val_str)
                        ph_values.append(ph_value)
                    except ValueError:
                        continue
    if ph_values:
        return {"pH_min": min(ph_values), "pH_max": max(ph_values)}
    else:
        return {"pH_min": None, "pH_max": None}

def build_usage_bar_data(event_aggregator, all_pumps):
    """Builds data for a usage bar chart.
       Returns a dict with a sorted list of dates and for each pump, a list of usage values.
    """
    dates = sorted(event_aggregator.keys())
    usage_data = {}
    for pump in all_pumps:
        usage_data[pump] = []
        for date in dates:
            usage = event_aggregator.get(date, {}).get(pump, 0)
            usage_data[pump].append(usage)
    return {"dates": dates, "usage_data": usage_data}

def get_recent_interesting_events():
    """Returns the 5 most recent events from hydro_events.csv."""
    events_csv = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    interesting = []
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            events = list(reader)
            events.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S") if len(x) > 0 else datetime.min, reverse=True)
            interesting = events[:5]
    return interesting

# Utility to dose volume in mL
def dose_volume(pump_name, ml_amount):
    """Dose a specified volume (in mL) using the specified pump."""
    try:
        dose_pump(pump_name, ml_amount)
        log_event("pump", f"Manually dosed {ml_amount} mL using pump {pump_name}")
        return True
    except Exception as e:
        log_event("pump", f"Error dosing pump {pump_name}: {e}")
        return False

# --- Camera Routes ---

@app.route('/video_feed')
def video_feed():
    """Video streaming route"""
    return Response(generate_frames(camera),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/take_snapshot', methods=['POST'])
def take_snapshot():
    """Take a snapshot"""
    try:
        filepath = camera.take_snapshot()
        log_event("camera", f"Snapshot taken: {filepath}")
        return {'status': 'success', 'filepath': filepath}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/snapshots')
def list_snapshots():
    """List available snapshots"""
    try:
        files = os.listdir('data/snapshots')
        files.sort(reverse=True)  # Most recent first
        return {'status': 'success', 'snapshots': files}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/snapshots/<path:filename>')
def serve_snapshot(filename):
    """Serve snapshot images"""
    return send_from_directory('data/snapshots', filename)

# --- Main Dashboard Route ---

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """Dashboard route displaying sensor and event data"""
    global GLOBAL_CONFIG
    message = ""

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "manual_pump":
            # Example: manually dose a pump with 10 mL
            pump_name = request.form.get("pump_name")
            if pump_name:
                success = dose_volume(pump_name, 10)
                message = f"Manual pump dose {'succeeded' if success else 'failed'} for pump {pump_name}."
        elif action == "volume_dose":
            # Example: dose a pump with a specified volume
            pump_name = request.form.get("pump_name")
            ml_amount = request.form.get("ml_amount")
            try:
                ml_amount = float(ml_amount)
                success = dose_volume(pump_name, ml_amount)
                message = f"Volume dosing {'succeeded' if success else 'failed'} for pump {pump_name}."
            except ValueError:
                message = "Invalid volume specified."
        # Add additional POST handlers as needed

    # Gather sensor data for charts
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
    ph_data = ph_data[-20:]  # Show only last 20 readings
    ec_data = ec_data[-20:]

    # Get event data
    event_aggregator = aggregate_event_data() or {}
    all_pumps = set()
    for date_str, usage_map in event_aggregator.items():
        for p in usage_map.keys():
            all_pumps.add(p)
    all_pumps = sorted(all_pumps)
    usage_bar_data = build_usage_bar_data(event_aggregator, all_pumps)
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    daily_pump_usage = 0
    if today_str in event_aggregator:
        daily_pump_usage = sum(event_aggregator[today_str].values())

    sensor_today = aggregate_sensor_data_for_today()
    daily_pH_min = sensor_today["pH_min"]
    daily_pH_max = sensor_today["pH_max"]

    interesting_events = get_recent_interesting_events()

    # Events pagination
    page = int(request.args.get("page", "1"))
    page_size = 25
    event_rows = []
    events_csv = os.path.join(os.path.dirname(__file__), "data", "hydro_events.csv")
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            rr = csv.reader(f)
            header = next(rr, None)
            event_rows = list(rr)
    event_rows.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S") if len(x) > 0 else datetime.min, reverse=True)
    total_events = len(event_rows)
    start_i = (page - 1) * page_size
    end_i = start_i + page_size
    event_rows = event_rows[start_i:end_i]
    has_next_page = (end_i < total_events)
    has_prev_page = (page > 1)

    # Build a simple usage summary for the dashboard
    summary_list = []
    for date_str in sorted(event_aggregator.keys()):
        summary_list.append({
            "date": date_str,
            "usage": event_aggregator[date_str]
        })

    return render_template(
        "dashboard.html",
        message=message,
        ph_data=ph_data,
        ec_data=ec_data,
        summary_list=summary_list,
        event_rows=event_rows,
        current_page=page,
        has_next_page=has_next_page,
        has_prev_page=has_prev_page,
        total_events=total_events,
        config=GLOBAL_CONFIG,
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
    # Initialize components
    init_pumps()
    init_event_log()
    init_sensor_log()
    load_config()

    # Create sensor object
    sensor_obj = SensorReader(i2c_bus=1, ph_address=0x63, ec_address=0x64)

    # Initialize and start the camera
    camera = PlantCamera(snapshot_dir='data/snapshots')
    camera.start()

    # Start sensor logging in a separate thread
    def run_logger():
        start_continuous_logging(sensor_obj, interval=10)
    t = threading.Thread(target=run_logger, daemon=True)
    t.start()

    # Run Flask
    app.run(host="0.0.0.0", port=5001, debug=True)


