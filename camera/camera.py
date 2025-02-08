from picamera2 import Picamera2
import io
import os
import time
from datetime import datetime, timedelta  # Added timedelta import
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
