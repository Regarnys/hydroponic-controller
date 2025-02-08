#!/usr/bin/env python3
from flask import Blueprint, request, jsonify

automation_bp = Blueprint('automation', __name__, template_folder='../templates')

# In-memory sample automation configuration (stub)
automation_config = {
    "schedules": {
        "image_capture": {
            "enabled": True,
            "interval_minutes": 60
        },
        "timelapse": {
            "enabled": False,
            "interval_minutes": 60,
            "duration_hours": 24
        }
    },
    "triggers": {
        "plant_health": {
            "enabled": True,
            "thresholds": {
                "min_green_percent": 30
            }
        }
    }
}

@automation_bp.route('/config', methods=['POST'])
def update_automation_config():
    global automation_config
    data = request.get_json()
    if data:
        # Update the automation configuration with provided data
        automation_config.update(data)
        return jsonify({"status": "success", "config": automation_config})
    return jsonify({"status": "error", "message": "No data provided"}), 400

@automation_bp.route('/status', methods=['GET'])
def automation_status():
    # Return the automation config and a dummy plant health status.
    plant_health = {
        "green_percentage": 75.0,
        "timestamp": "2025-02-08T12:00:00"
    }
    return jsonify({"status": "success", "config": automation_config, "plant_health": plant_health})
