# File: camera/camera.py

from picamera2 import Picamera2
import os
import time
from datetime import datetime, timedelta
import threading
import cv2
import numpy as np

class PlantCamera:
    def __init__(self, snapshot_dir='data/snapshots',
                 timelapse_dir='data/timelapse',
                 resolution=(1920, 1080)):
        """
        Initialize the camera for on-demand still capture.
        This version does NOT run a continuous capture loop.
        """
        self.snapshot_dir = snapshot_dir
        self.timelapse_dir = timelapse_dir
        self.resolution = resolution
        self._picam = None
        self._initialized = False

        # Create directories if they don't exist.
        for directory in [self.snapshot_dir, self.timelapse_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        # Optionally, run any cleanup commands if needed.
        cleanup_commands = [
            "sudo pkill -f 'python3.*camera'",
            "sudo pkill -f 'libcamera'",
            "sudo pkill -f 'rpicam'",
            "sudo rm -f /dev/shm/camera*"
        ]
        for cmd in cleanup_commands:
            try:
                os.system(cmd)
                time.sleep(0.5)
            except Exception as e:
                print(f"Cleanup command failed: {e}")

        time.sleep(2)  # Give extra time for cleanup.
        self.setup_camera()

    def setup_camera(self):
        """
        Initialize the camera for on-demand still capture.
        This uses a still configuration.
        """
        try:
            self._picam = Picamera2()
            config = self._picam.create_still_configuration(
                main={"size": self.resolution, "format": "RGB888"}
            )
            self._picam.configure(config)
            print("Camera initialized successfully for on-demand capture")
            self._initialized = True
        except Exception as e:
            print(f"Camera initialization failed: {e}")
            self._initialized = False

    def capture_single_frame(self):
        """
        Capture and return a single frame from the camera.
        This method is used on demand when a snapshot is requested.
        """
        try:
            frame = self._picam.capture_array()
            return frame
        except Exception as e:
            print(f"Error capturing frame: {e}")
            return None

    def take_snapshot(self, filename=None):
        """
        Capture a snapshot on demand and save it as a JPEG file in the snapshots folder.
        """
        frame = self.capture_single_frame()
        if frame is None:
            print("No frame available for snapshot.")
            return None
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'snapshot_{timestamp}.jpg'
        filepath = os.path.join(self.snapshot_dir, filename)
        success = cv2.imwrite(filepath, frame)
        if success:
            print(f"Snapshot saved to {filepath}")
            return filepath
        else:
            print("Failed to write snapshot to file.")
            return None

    def start_timelapse(self, interval_minutes=60, duration_hours=24):
        """
        Start a timelapse capture that takes snapshots at defined intervals.
        This runs in a background thread.
        """
        def _timelapse_loop():
            end_time = datetime.now() + timedelta(hours=duration_hours)
            while datetime.now() < end_time:
                self.take_snapshot()
                time.sleep(interval_minutes * 60)
        threading.Thread(target=_timelapse_loop, daemon=True).start()
        print(f"Started timelapse: {interval_minutes} minute intervals for {duration_hours} hours")

    # Optionally, if you need a live preview for your dashboard,
    # you can use the methods below to capture a frame on demand.
    def get_frame(self):
        """
        Capture a single frame and return it encoded as JPEG.
        This can be used to provide a live preview (MJPEG) on the dashboard.
        """
        frame = self.capture_single_frame()
        if frame is None:
            return None
        try:
            # (Optionally, convert color if needed. Here we assume the frame is RGB.)
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                return jpeg.tobytes()
            else:
                print("Failed to encode frame as JPEG")
                return None
        except Exception as e:
            print(f"Error encoding frame: {e}")
            return None

def generate_frames(camera):
    """
    Generator function for MJPEG live preview.
    Each time a frame is requested, capture it on demand.
    (Note: This may have lower frame rate performance compared to a continuous loop.)
    """
    while True:
        frame = camera.get_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            time.sleep(0.1)


