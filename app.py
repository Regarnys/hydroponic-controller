# File: app.py

from flask import Flask, render_template, request, redirect, url_for, Response, send_from_directory
import csv
import os
import json
import time
from datetime import datetime
import threading

# Import modules
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

# Global config
CONFIG_FILE = "config.json"
GLOBAL_CONFIG = {
    "ph_min": 5.8,
    "ph_max": 6.2,
    "ec_min": 1.0,
    "pump_calibration": {}
}

def load_config():
    """Load system-wide configuration from JSON file."""
    global GLOBAL_CONFIG
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            loaded = json.load(f)
            GLOBAL_CONFIG.update(loaded)

def save_config():
    """Save updated system-wide configuration."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(GLOBAL_CONFIG, f, indent=2)

# --- Camera Initialization ---

camera = None  # Define globally to avoid errors

def initialize_camera():
    """Initialize the camera and handle failures."""
    global camera
    try:
        camera = PlantCamera(snapshot_dir='data/snapshots')
        if camera._initialized:
            print("✅ Camera initialized successfully.")
        else:
            print("❌ Camera failed to initialize.")
            camera = None  # Prevent invalid camera usage
    except Exception as e:
        print(f"❌ Error initializing camera: {e}")
        camera = None  # Set to None to avoid crashes

# --- Camera Routes ---

@app.route('/video_feed')
def video_feed():
    """Live video feed from the plant camera."""
    if camera is None or not camera._initialized:
        print("🚨 Camera not initialized for video feed.")
        return "Camera not initialized", 500

    return Response(generate_frames(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/take_snapshot', methods=['POST'])
def take_snapshot():
    """Take a snapshot from the camera."""
    if camera is None or not camera._initialized:
        return {'status': 'error', 'message': 'Camera not initialized'}

    try:
        filepath = camera.take_snapshot()
        log_event("camera", f"Snapshot taken: {filepath}")
        return {'status': 'success', 'filepath': filepath}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/snapshots')
def list_snapshots():
    """List all available snapshots."""
    try:
        files = os.listdir('data/snapshots')
        files.sort(reverse=True)
        return {'status': 'success', 'snapshots': files}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

@app.route('/snapshots/<path:filename>')
def serve_snapshot(filename):
    """Serve snapshot images."""
    return send_from_directory('data/snapshots', filename)

# --- Flask App Routes ---

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    """Dashboard route displaying sensor and event data."""
    global GLOBAL_CONFIG
    message = ""

    # Handle form submissions
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "manual_pump":
            pump_name = request.form.get("pump_name")
            success = dose_volume(pump_name, 10)
            message = f"Manual pump dose {'succeeded' if success else 'failed'} for pump {pump_name}."
        elif action == "volume_dose":
            pump_name = request.form.get("pump_name")
            ml_amount = request.form.get("ml_amount")
            try:
                ml_amount = float(ml_amount)
                success = dose_volume(pump_name, ml_amount)
                message = f"Volume dosing {'succeeded' if success else 'failed'} for pump {pump_name}."
            except ValueError:
                message = "Invalid volume specified."

    # Collect sensor data
    ph_data, ec_data = [], []
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
    ph_data = ph_data[-20:]  # Show last 20 readings
    ec_data = ec_data[-20:]

    # Fetch event data
    event_aggregator = aggregate_event_data() or {}
    usage_bar_data = build_usage_bar_data(event_aggregator, list(event_aggregator.keys()))
    
    sensor_today = aggregate_sensor_data_for_today()
    daily_pH_min = sensor_today["pH_min"]
    daily_pH_max = sensor_today["pH_max"]

    interesting_events = get_recent_interesting_events()

    return render_template(
        "dashboard.html",
        message=message,
        ph_data=ph_data,
        ec_data=ec_data,
        usage_bar_data=usage_bar_data,
        interesting_events=interesting_events,
        daily_pH_min=daily_pH_min,
        daily_pH_max=daily_pH_max
    )

@app.route("/")
def index():
    return redirect(url_for("dashboard"))

# --- Main Execution ---

if __name__ == "__main__":
    print("🔧 Initializing system components...")
    
    # Initialize hardware components
    init_pumps()
    init_event_log()
    init_sensor_log()
    load_config()

    # Start camera safely
    initialize_camera()

    # Create sensor object
    sensor_obj = SensorReader(i2c_bus=1, ph_address=0x63, ec_address=0x64)

    # Start sensor logging in a background thread
    def run_logger():
        start_continuous_logging(sensor_obj, interval=10)
    t = threading.Thread(target=run_logger, daemon=True)
    t.start()

    print("🚀 Starting Flask server...")
    app.run(host="0.0.0.0", port=5001, debug=True)


