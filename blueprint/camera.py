#!/usr/bin/env python3
from flask import Blueprint, Response, jsonify, request, render_template, send_from_directory
from camera.camera import PlantCamera, generate_frames

camera_bp = Blueprint('camera', __name__, template_folder='../templates')

# Initialize and start the camera (could also be done in app.py)
camera = PlantCamera(snapshot_dir='data/snapshots')
camera.start()

@camera_bp.route("/video_feed")
def video_feed():
    return Response(generate_frames(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@camera_bp.route("/take_snapshot", methods=["POST"])
def take_snapshot():
    try:
        filepath = camera.take_snapshot()
        return jsonify({"status": "success", "filepath": filepath})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@camera_bp.route("/")
def camera_dashboard():
    return render_template("camera.html")

@camera_bp.route("/snapshots/<path:filename>")
def serve_snapshot(filename):
    return send_from_directory('data/snapshots', filename)
