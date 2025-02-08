# File: camera/camera.py
from picamera2 import Picamera2
import io
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

        # Create directories
        for directory in [snapshot_dir, timelapse_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

        # Kill any existing camera processes
        os.system("sudo pkill -f 'python3.*camera'")
        time.sleep(2)  # Give time for cleanup

        # Initialize camera
        self._initialized = self.setup_camera()

    def setup_camera(self):
        """Initialize the IMX500 Camera with optimal settings"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Clean up any existing instance
                if self._picam:
                    try:
                        self._picam.stop()
                        self._picam.close()
                    except:
                        pass
                    self._picam = None
                
                time.sleep(2)  # Give camera time to release
                
                # Initialize new camera instance
                self._picam = Picamera2()
                
                # Configure for IMX500
                config = self._picam.create_preview_configuration(
                    main={"size": self.resolution, "format": "RGB888"},
                    buffer_count=2
                )
                self._picam.configure(config)
                
                # Configure camera with more conservative settings
                self._picam.set_controls({
                    "FrameDurationLimits": (33333, 33333),  # ~30fps
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
                        except:
                            pass
                        self._picam = None
                    return False
                time.sleep(2)  # Wait before retrying
            
    def start(self):
        """Start the camera and frame capture thread"""
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
        """Stop the camera"""
        self._running = False
        if self._picam:
            try:
                self._picam.stop()
                self._picam.close()
                self._picam = None
            except Exception as e:
                print(f"Error stopping camera: {e}")

    def _capture_loop(self):
        """Continuous capture loop for streaming"""
        frame_count = 0
        while self._running:
            try:
                frame = self._picam.capture_array()
                with self._lock:
                    self._last_frame = frame
                frame_count += 1
                if frame_count % 100 == 0:  # Log every 100 frames
                    print(f"Captured {frame_count} frames")
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"Error in capture loop: {str(e)}")
                time.sleep(1)

    def get_frame(self):
        """Get the latest frame as JPEG bytes"""
        if self._last_frame is None:
            return None

        try:
            with self._lock:
                frame = self._last_frame.copy()
            
            # Convert BGR to RGB if needed
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            ret, jpeg = cv2.imencode('.jpg', frame)
            return jpeg.tobytes() if ret else None
        except Exception as e:
            print(f"Error encoding frame: {str(e)}")
            return None

    def take_snapshot(self, filename=None):
        """Take a high-quality snapshot"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'snapshot_{timestamp}.jpg'

            filepath = os.path.join(self.snapshot_dir, filename)
            
            # Use capture_file for better quality
            self._picam.capture_file(filepath)
            print(f"Snapshot saved to {filepath}")
            return filepath
        except Exception as e:
            print(f"Error taking snapshot: {str(e)}")
            return None

    # Rest of your methods remain the same (start_timelapse, analyze_plant_health, etc.)
