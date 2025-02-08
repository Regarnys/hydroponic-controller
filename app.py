#!/usr/bin/env python3
"""
Main application entry point.
This app uses Flask with modular blueprints for sensors, pumps, camera, events, config, and automation.
It also reads sensor and event data from CSV files.
"""

from flask import Flask, render_template
from blueprints.sensors import sensors_bp
from blueprints.pumps import pumps_bp
from blueprints.camera import camera_bp
from blueprints.events import events_bp
from blueprints.config import config_bp
from blueprints.automation import automation_bp
import json
import os
import csv
from datetime import datetime

# Global configuration file and default values
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

# Data file paths
DATA_DIR = "/home/nikita/hydroponic-controller/data"
SENSOR_CSV = os.path.join(DATA_DIR, "sensor_data.csv")
EVENTS_CSV = os.path.join(DATA_DIR, "hydro_events.csv")

# Helper function: Aggregate sensor data for today (for pH readings)
def aggregate_sensor_data_for_today():
    today = datetime.now().strftime("%Y-%m-%d")
    ph_values = []
    if os.path.exists(SENSOR_CSV):
        with open(SENSOR_CSV, "r", encoding="utf-8") as f:
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
                        ph_val = float(val_str)
                        ph_values.append(ph_val)
                    except ValueError:
                        continue
    if ph_values:
        return min(ph_values), max(ph_values)
    else:
        return None, None

# Helper function: Aggregate event data from the hydro events CSV
def aggregate_event_data():
    aggregator = {}
    if os.path.exists(EVENTS_CSV):
        with open(EVENTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
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
                aggregator.setdefault(date_str, {})
                aggregator[date_str][pump] = aggregator[date_str].get(pump, 0) + usage
    return aggregator

# Helper function: Get total pump usage for today
def get_daily_pump_usage(aggregator):
    today_str = datetime.now().strftime("%Y-%m-%d")
    if today_str in aggregator:
        return sum(aggregator[today_str].values())
    return 0

# Helper function: Get the 5 most recent events
def get_recent_interesting_events():
    events = []
    if os.path.exists(EVENTS_CSV):
        with open(EVENTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            events = list(reader)
        events.sort(key=lambda x: datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S") if x[0] else datetime.min, reverse=True)
        return events[:5]
    return events

# Helper function: Get recent sensor readings for a given sensor (default count=20)
def get_recent_sensor_readings(sensor_name, count=20):
    readings = []
    if os.path.exists(SENSOR_CSV):
        with open(SENSOR_CSV, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                ts_str, name, val_str = row[:3]
                if name == sensor_name:
                    try:
                        value = float(val_str)
                        readings.append([ts_str, value])
                    except ValueError:
                        continue
    return readings[-count:]

# Helper function: Build usage bar chart data from event aggregator
def build_usage_bar_data(aggregator):
    dates = sorted(aggregator.keys())
    usage_data = {}
    all_pumps = set()
    for date in dates:
        for pump in aggregator[date].keys():
            all_pumps.add(pump)
    all_pumps = sorted(all_pumps)
    for pump in all_pumps:
        usage_data[pump] = []
        for date in dates:
            usage_data[pump].append(aggregator.get(date, {}).get(pump, 0))
    return {"dates": dates, "usage_data": usage_data}, all_pumps

app = Flask(__name__)

# Register blueprints with URL prefixes
app.register_blueprint(sensors_bp, url_prefix="/sensors")
app.register_blueprint(pumps_bp, url_prefix="/pumps")
app.register_blueprint(camera_bp, url_prefix="/camera")
app.register_blueprint(events_bp, url_prefix="/events")
app.register_blueprint(config_bp, url_prefix="/config")
app.register_blueprint(automation_bp, url_prefix="/automation")

# Main dashboard route – it now reads data from the CSV files.
@app.route("/")
def index():
    # Get today's pH min and max
    daily_pH_min, daily_pH_max = aggregate_sensor_data_for_today()
    # Aggregate hydro events
    aggregator = aggregate_event_data()
    # Calculate today's total pump usage
    daily_pump_usage = get_daily_pump_usage(aggregator)
    # Get the 5 most recent interesting events
    interesting_events = get_recent_interesting_events()
    # Get the last 20 sensor readings for pH and EC
    ph_data = get_recent_sensor_readings("pH", 20)
    ec_data = get_recent_sensor_readings("EC", 20)
    # Build data for a usage bar chart and get list of all pumps
    usage_bar_data, all_pumps = build_usage_bar_data(aggregator)
    
    return render_template("dashboard.html",
                           config=GLOBAL_CONFIG,
                           daily_pH_min=daily_pH_min,
                           daily_pH_max=daily_pH_max,
                           daily_pump_usage=daily_pump_usage,
                           interesting_events=interesting_events,
                           ph_data=ph_data,
                           ec_data=ec_data,
                           usage_bar_data=usage_bar_data,
                           all_pumps=all_pumps)

if __name__ == "__main__":
    load_config()
    app.run(host="0.0.0.0", port=5001, debug=True)


