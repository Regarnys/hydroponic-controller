#!/usr/bin/env python3
from flask import Blueprint, render_template, request
import json
import os

config_bp = Blueprint('config', __name__, template_folder='../templates')

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
    return GLOBAL_CONFIG

@config_bp.route("/", methods=["GET", "POST"])
def config_page():
    message = ""
    if request.method == "POST":
        try:
            GLOBAL_CONFIG["ph_min"] = float(request.form.get("ph_min"))
            GLOBAL_CONFIG["ph_max"] = float(request.form.get("ph_max"))
            GLOBAL_CONFIG["ec_min"] = float(request.form.get("ec_min"))
            with open(CONFIG_FILE, "w") as f:
                json.dump(GLOBAL_CONFIG, f, indent=2)
            message = "Config updated successfully."
        except Exception as e:
            message = f"Error updating config: {e}"
    config = load_config()
    return render_template("config.html", config=config, message=message)

