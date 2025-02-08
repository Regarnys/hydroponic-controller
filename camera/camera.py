# File: camera/camera.py
from picamera2 import Picamera2
import io
import os
import time
from datetime import datetime
import threading
import cv2
import numpy as np


class PlantCamera:
    def __init__(self, snapshot_dir='data/snapshots',
                 timelapse_dir='data/timelapse',
                 resolution=(1920, 1080)):
        self.snapshot_dir = snapshot_dir
        self.timelapse_dir = timelapse_dir
        self.resolution = resolution
        self._picam = None
        self._running = False
        self._lock = threading.Lock()
        self._last_frame = None

        # Create directories
        for directory in [snapshot_dir, timelapse_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        # Initialize camera
        self.setup_camera()

    def setup_camera(self):
    """Initialize the Pi Camera with optimal settings for plants"""
    max_retries = 3
        for attempt in range(max_retries):
            try:
                if self._picam:
                    self._picam.close()
            
                time.sleep(2)  # Give camera time to release
                self._picam = Picamera2()
            
                config = self._picam.create_preview_configuration(
                    main={"size": self.resolution},
                    buffer_count=2
                )
                self._picam.configure(config)
            
                # Configure camera for good plant imaging
                self._picam.set_controls({
                    "ExposureTime": 10000,  # 10ms exposure
                    "AnalogueGain": 1.0,    # Base ISO
                    "AeEnable": True,       # Auto exposure
                    "AwbEnable": True,      # Auto white balance
                })
            
            return True
        except Exception as e:
            print(f"Camera initialization attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                print("Failed to initialize camera after multiple attempts")
                return False
            time.sleep(2)  # Wait before retrying
    def start(self):
        """Start the camera and frame capture thread"""
        if self._running:
            return

        self._picam.start()
        self._running = True
        threading.Thread(target=self._capture_loop, daemon=True).start()

    def stop(self):
        """Stop the camera"""
        self._running = False
        if self._picam:
            self._picam.stop()

    def _capture_loop(self):
        """Continuous capture loop for streaming"""
        while self._running:
            frame = self._picam.capture_array()
            with self._lock:
                self._last_frame = frame
            time.sleep(0.1)  # 10 FPS is plenty for plants

    def get_frame(self):
        """Get the latest frame as JPEG bytes"""
        if self._last_frame is None:
            return None

        with self._lock:
            frame = self._last_frame.copy()

        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes() if ret else None

    def take_snapshot(self, filename=None):
        """Take a high-quality snapshot"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'snapshot_{timestamp}.jpg'

        filepath = os.path.join(self.snapshot_dir, filename)
        self._picam.capture_file(filepath)
        return filepath

    def start_timelapse(self, interval_minutes=60, duration_hours=24):
        """Start a timelapse capture thread"""

        def _timelapse_loop():
            end_time = datetime.now() + timedelta(hours=duration_hours)
            while datetime.now() < end_time and self._running:
                filename = f'timelapse_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'
                self.take_snapshot(filename)
                time.sleep(interval_minutes * 60)

        threading.Thread(target=_timelapse_loop, daemon=True).start()

    def analyze_plant_health(self, frame=None):
        """Basic plant health analysis using color thresholds"""
        if frame is None:
            with self._lock:
                if self._last_frame is None:
                    return None
                frame = self._last_frame.copy()

        # Convert to HSV for better color analysis
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Define green color range
        lower_green = np.array([35, 30, 30])
        upper_green = np.array([85, 255, 255])

        # Create mask for green pixels
        green_mask = cv2.inRange(hsv, lower_green, upper_green)

        # Calculate percentage of green pixels
        green_percent = (np.count_nonzero(green_mask) / green_mask.size) * 100

        return {
            'green_percentage': green_percent,
            'timestamp': datetime.now().isoformat()
        }


def generate_frames(camera):
    """Generator function for Flask video streaming"""
    while True:
        frame = camera.get_frame()
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
