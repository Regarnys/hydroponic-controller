#!/usr/bin/env python3
from flask import Blueprint, jsonify, request, render_template
from pumps.pumps import dose_pump, pump_pins
import RPi.GPIO as GPIO

pumps_bp = Blueprint('pumps', __name__, template_folder='../templates')

@pumps_bp.route("/")
def pump_control_page():
    return render_template("pump_control.html", pump_names=list(pump_pins.keys()))

@pumps_bp.route("/dose", methods=["POST"])
def dose_pump_route():
    pump_name = request.form.get("pump_name")
    seconds = float(request.form.get("seconds", 0))
    try:
        dose_pump(pump_name, seconds)
        return jsonify({"status": "success", "message": f"Pump {pump_name} dosed for {seconds} seconds."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Manual Pump Control page
@pumps_bp.route("/manual", methods=["GET", "POST"])
def manual_control():
    message = ""
    if request.method == "POST":
        pump_name = request.form.get("pump_name")
        run_seconds = request.form.get("run_seconds")
        try:
            run_seconds = float(run_seconds)
            dose_pump(pump_name, run_seconds)
            message = f"Pump {pump_name} run for {run_seconds} seconds."
        except Exception as e:
            message = str(e)
    return render_template("manual.html", pump_names=list(pump_pins.keys()), message=message)

# Calibrate Pump page
@pumps_bp.route("/calibrate", methods=["GET", "POST"])
def calibrate():
    message = ""
    # For demonstration, we assume calibration data is stored in config.
    from blueprints.config import GLOBAL_CONFIG
    if request.method == "POST":
        action = request.form.get("action")
        pump_name = request.form.get("pump_name")
        if action == "test_run":
            test_run_seconds = float(request.form.get("test_run_seconds", 5))
            try:
                dose_pump(pump_name, test_run_seconds)
                message = f"Test run on {pump_name} for {test_run_seconds} seconds completed."
            except Exception as e:
                message = f"Error during test run: {e}"
        elif action == "save_measurement":
            test_run_seconds = request.form.get("test_run_seconds")
            measured_ml = request.form.get("measured_ml")
            GLOBAL_CONFIG.setdefault("pump_calibration", {})[pump_name] = {
                "test_run_seconds": test_run_seconds,
                "measured_ml": measured_ml
            }
            message = f"Calibration for {pump_name} saved."
    return render_template("calibrate.html", pump_names=list(pump_pins.keys()),
                           message=message, config=GLOBAL_CONFIG)
