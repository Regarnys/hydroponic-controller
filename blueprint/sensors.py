#!/usr/bin/env python3
from flask import Blueprint, jsonify, render_template
from sensors import SensorReader

sensors_bp = Blueprint('sensors', __name__, template_folder='../templates')

@sensors_bp.route("/")
def get_sensors_data():
    sensor = SensorReader()
    ph = sensor.read_ph_sensor()
    ec = sensor.read_ec_sensor()
    sensor.close()
    return jsonify({
        "ph": ph,
        "ec": ec
    })

@sensors_bp.route("/dashboard")
def sensors_dashboard():
    # Render a page with sensor charts (implement JS/charting as needed)
    return render_template("sensors.html")
