#!/usr/bin/env python3
from flask import Blueprint, jsonify, request, render_template
from pumps.pumps import dose_pump

pumps_bp = Blueprint('pumps', __name__, template_folder='../templates')

@pumps_bp.route("/")
def pump_control_page():
    return render_template("pump_control.html")

@pumps_bp.route("/dose", methods=["POST"])
def dose_pump_route():
    pump_name = request.form.get("pump_name")
    seconds = float(request.form.get("seconds", 0))
    try:
        dose_pump(pump_name, seconds)
        return jsonify({"status": "success", "message": f"Pump {pump_name} dosed for {seconds} seconds."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})
