#!/usr/bin/env python3
from flask import Blueprint, jsonify, render_template
from sensors import SensorReader
import csv
import os

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

# Override the endpoint name so that url_for('sensors.dashboard') works.
@sensors_bp.route("/dashboard", endpoint="dashboard")
def sensors_dashboard():
    return render_template("sensors.html")

@sensors_bp.route("/data")
def sensor_data_page():
    sensor_data = []
    sensor_csv = os.path.join(os.path.dirname(__file__), "../data/sensor_data.csv")
    if os.path.exists(sensor_csv):
        with open(sensor_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            sensor_data = list(reader)
    return render_template("sensors_data.html", sensor_data=sensor_data)
