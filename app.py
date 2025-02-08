#!/usr/bin/env python3
"""
Main application entry point.
This app uses Flask with modular blueprints for sensors, pumps, camera, events, and config.
"""

from flask import Flask, render_template
from blueprints.sensors import sensors_bp
from blueprints.pumps import pumps_bp
from blueprints.camera import camera_bp
from blueprints.events import events_bp
from blueprints.config import config_bp
import json
import os

# Global configuration
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

app = Flask(__name__)

# Register blueprints with URL prefixes
app.register_blueprint(sensors_bp, url_prefix="/sensors")
app.register_blueprint(pumps_bp, url_prefix="/pumps")
app.register_blueprint(camera_bp, url_prefix="/camera")
app.register_blueprint(events_bp, url_prefix="/events")
app.register_blueprint(config_bp, url_prefix="/config")

# Main dashboard route (uses index.html)
@app.route("/")
def index():
    return render_template("index.html", config=GLOBAL_CONFIG)

if __name__ == "__main__":
    load_config()
    app.run(host="0.0.0.0", port=5001, debug=True)



