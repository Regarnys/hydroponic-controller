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
        self.snapshot_dir = snapshot_dir
        self.timelapse_dir = timelapse_dir
        self.resolution = resolution
        self._picam = None
        self._running = False
        self._lock = threading.Lock()
        self._last_frame = None
        self._initialized = False

        # Create directories if they don't exist
        for directory in [snapshot_dir, timelapse_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        # Cleanup any processes that might be using the camera
        cleanup_commands = [
            "sudo pkill -f 'python3.*camera'",
            "sudo pkill -f 'libcamera'",
            "sudo pkill -f 'rpicam'",
            # Removed the picamera2 service restart because it was not found
            "sudo rm -f /dev/shm/camera*"
        ]
        for cmd in cleanup_commands:
            try:
                os.system(cmd)
                time.sleep(0.5)
            except Exception as e:
                print(f"Cleanup command failed: {e}")

        time.sleep(2)  # Extra delay for cleanup
        self._initialized = self.setup_camera()

    def setup_camera(self):
        """Initialize the camera with the specified resolution and settings."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self._picam:
                    try:
                        self._picam.stop()
                        self._picam.close()
                    except Exception as e:
                        print(f"Error closing previous camera instance: {e}")
                    self._picam = None

                time.sleep(2)
                self._picam = Picamera2()

                config = self._picam.create_preview_configuration(
                    main={"size": self.resolution, "format": "RGB888"},
                    buffer_count=2
                )
                self._picam.configure(config)

                # Set camera controls (aiming for ~30 FPS)
                self._picam.set_controls({
                    "FrameDurationLimits": (33333, 33333),
                    "AeEnable": True,
                    "AwbEnable": True,
                    "FrameRate": 30.0
                })

                print("Camera initialized successfully")
                return True

            except Exception as e:
                print(f"Camera initialization attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    print("Failed to initialize camera after multiple attempts")
                    if self._picam:
                        try:
                            self._picam.close()
                        except Exception as e:
                            print(f"Error closing camera: {e}")
                        self._picam = None
                    return False
                time.sleep(2)

    def start(self):
        """Start the camera capture loop."""
        if self._running:
            return False

        if not self._initialized or not self._picam:
            print("Camera not properly initialized. Attempting to reinitialize...")
            self._initialized = self.setup_camera()
            if not self._initialized:
                print("Failed to initialize camera")
                return False

        try:
            self._picam.start()
            self._running = True
            threading.Thread(target=self._capture_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"Error starting camera: {e}")
            self._running = False
            return False

    def stop(self):
        """Stop the camera."""
        self._running = False
        if self._picam:
            try:
                self._picam.stop()
                self._picam.close()
                self._picam = None
            except Exception as e:
                print(f"Error stopping camera: {e}")

    def _capture_loop(self):
        """Continuously capture frames for the live feed."""
        frame_count = 0
        while self._running:
            try:
                frame = self._picam.capture_array()
                if frame is not None:
                    with self._lock:
                        self._last_frame = frame
                    frame_count += 1
                    if frame_count % 100 == 0:
                        print(f"Captured {frame_count} frames")
                else:
                    print("No frame returned by capture_array()")
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"Error in capture loop: {str(e)}")
                time.sleep(1)

    def get_frame(self):
        """Return the latest frame encoded as JPEG."""
        if self._last_frame is None:
            return None

        try:
            with self._lock:
                frame = self._last_frame.copy()
            # Convert color if necessary (Picamera2 usually returns BGR)
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            ret, jpeg = cv2.imencode('.jpg', frame)
            if ret:
                return jpeg.tobytes()
            else:
                print("Failed to encode frame as JPEG")
                return None
        except Exception as e:
            print(f"Error encoding frame: {str(e)}")
            return None

    def take_snapshot(self, filename=None):
        """Capture a high-quality snapshot and save it."""
        try:
            if not self._picam:
                print("Camera instance is not available for snapshot.")
                return None
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'snapshot_{timestamp}.jpg'
            filepath = os.path.join(self.snapshot_dir, filename)
            self._picam.capture_file(filepath)
            print(f"Snapshot saved to {filepath}")
            return filepath
        except Exception as e:
            print(f"Error taking snapshot: {str(e)}")
            return None

    def start_timelapse(self, interval_minutes=60, duration_hours=24):
        """Start capturing snapshots at intervals for a timelapse."""
        def _timelapse_loop():
            end_time = datetime.now() + timedelta(hours=duration_hours)
            while datetime.now() < end_time and self._running:
                try:
                    filename = f'timelapse_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jpg'
                    filepath = os.path.join(self.timelapse_dir, filename)
                    self._picam.capture_file(filepath)
                    print(f"Timelapse frame captured: {filename}")
                except Exception as e:
                    print(f"Error in timelapse: {str(e)}")
                time.sleep(interval_minutes * 60)
        threading.Thread(target=_timelapse_loop, daemon=True).start()
        print(f"Started timelapse: {interval_minutes}min intervals for {duration_hours}hrs")

    def analyze_plant_health(self, frame=None):
        """Perform basic plant health analysis using color thresholds."""
        try:
            if frame is None:
                with self._lock:
                    if self._last_frame is None:
                        return None
                    frame = self._last_frame.copy()
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            lower_green = np.array([35, 30, 30])
            upper_green = np.array([85, 255, 255])
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            green_percent = (np.count_nonzero(green_mask) / green_mask.size) * 100
            return {
                'green_percentage': green_percent,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            print(f"Error analyzing plant health: {str(e)}")
            return None

def generate_frames(camera):
    """Generator for streaming JPEG frames to the web client."""
    while True:
        try:
            frame = camera.get_frame()
            if frame is not None:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # If no frame is available, pause briefly.
                time.sleep(0.1)
        except Exception as e:
            print(f"Error generating frames: {str(e)}")
            time.sleep(1)

