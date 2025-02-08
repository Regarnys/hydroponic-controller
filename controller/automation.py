# File: controller/automation.py
from datetime import datetime, timedelta
import threading
import time
import json
import os
from data.logger import log_event, log_sensor


class AutomationController:
    def __init__(self, sensor_reader, camera, pump_controller, config_file='config/automation.json'):
        self.sensor_reader = sensor_reader
        self.camera = camera
        self.pump_controller = pump_controller
        self.config_file = config_file
        self.running = False
        self.tasks = {}
        self.load_config()

    def load_config(self):
        """Load automation configuration"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'schedules': {
                    'sensor_check': {
                        'enabled': True,
                        'interval_minutes': 30
                    },
                    'image_capture': {
                        'enabled': True,
                        'interval_minutes': 60
                    },
                    'timelapse': {
                        'enabled': False,
                        'interval_minutes': 60,
                        'duration_hours': 24
                    }
                },
                'triggers': {
                    'ph_control': {
                        'enabled': True,
                        'check_interval_minutes': 15,
                        'thresholds': {
                            'min': 5.8,
                            'max': 6.2
                        }
                    },
                    'ec_control': {
                        'enabled': True,
                        'check_interval_minutes': 15,
                        'thresholds': {
                            'min': 1.0
                        }
                    },
                    'plant_health': {
                        'enabled': True,
                        'check_interval_minutes': 60,
                        'thresholds': {
                            'min_green_percent': 30
                        }
                    }
                }
            }
            self.save_config()

    def save_config(self):
        """Save current configuration"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def start(self):
        """Start the automation controller"""
        if self.running:
            return

        self.running = True
        threading.Thread(target=self._automation_loop, daemon=True).start()

    def stop(self):
        """Stop the automation controller"""
        self.running = False

    def _automation_loop(self):
        """Main automation loop"""
        last_runs = {}  # Track last run time for each task

        while self.running:
            now = datetime.now()

            # Check scheduled tasks
            for task_name, settings in self.config['schedules'].items():
                if not settings.get('enabled', False):
                    continue

                interval = timedelta(minutes=settings['interval_minutes'])
                last_run = last_runs.get(task_name, datetime.min)

                if now - last_run >= interval:
                    self._run_scheduled_task(task_name)
                    last_runs[task_name] = now

            # Check triggers
            for trigger_name, settings in self.config['triggers'].items():
                if not settings.get('enabled', False):
                    continue

                interval = timedelta(minutes=settings['check_interval_minutes'])
                last_run = last_runs.get(f"trigger_{trigger_name}", datetime.min)

                if now - last_run >= interval:
                    self._check_trigger(trigger_name)
                    last_runs[f"trigger_{trigger_name}"] = now

            time.sleep(10)  # Check every 10 seconds

    def _run_scheduled_task(self, task_name):
        """Execute a scheduled task"""
        if task_name == 'sensor_check':
            self._check_and_log_sensors()
        elif task_name == 'image_capture':
            self._capture_and_analyze_image()
        elif task_name == 'timelapse':
            if not hasattr(self, '_timelapse_running'):
                self._start_timelapse()

    def _check_trigger(self, trigger_name):
        """Check and handle triggers"""
        if trigger_name == 'ph_control':
            self._check_ph_trigger()
        elif trigger_name == 'ec_control':
            self._check_ec_trigger()
        elif trigger_name == 'plant_health':
            self._check_plant_health()

    def _check_and_log_sensors(self):
        """Read and log sensor data"""
        # pH reading
        ph_val = self.sensor_reader.read_ph_sensor()
        if ph_val is not None:
            log_sensor("pH", ph_val)

        # EC reading
        ec_result = self.sensor_reader.read_ec_sensor()
        if ec_result and ec_result.get('ec'):
            log_sensor("EC", ec_result['ec'])

    def _capture_and_analyze_image(self):
        """Capture and analyze plant image"""
        if self.camera:
            health_data = self.camera.analyze_plant_health()
            if health_data:
                log_event('plant_analysis',
                          f"Green coverage: {health_data['green_percentage']:.1f}%")

    def _start_timelapse(self):
        """Start timelapse capture"""
        if self.camera:
            settings = self.config['schedules']['timelapse']
            self.camera.start_timelapse(
                interval_minutes=settings['interval_minutes'],
                duration_hours=settings['duration_hours']
            )
            self._timelapse_running = True

    def _check_ph_trigger(self):
        """Check and adjust pH if needed"""
        ph_val = self.sensor_reader.read_ph_sensor()
        if ph_val is None:
            return

        thresholds = self.config['triggers']['ph_control']['thresholds']

        if ph_val < thresholds['min']:
            self.pump_controller.dose_volume('pH_up', 1.0)  # 1ml dose
            log_event('auto_ph', f'Low pH ({ph_val}) - dosed pH up')
        elif ph_val > thresholds['max']:
            self.pump_controller.dose_volume('pH_down', 1.0)  # 1ml dose
            log_event('auto_ph', f'High pH ({ph_val}) - dosed pH down')

    def _check_ec_trigger(self):
        """Check and adjust EC if needed"""
        ec_result = self.sensor_reader.read_ec_sensor()
        if not ec_result or 'ec' not in ec_result:
            return

        ec_val = ec_result['ec']
        threshold = self.config['triggers']['ec_control']['thresholds']['min']

        if ec_val < threshold:
            # Dose all nutrients in sequence
            for pump in ['nutrientA', 'nutrientB', 'nutrientC']:
                self.pump_controller.dose_volume(pump, 2.0)  # 2ml each
                time.sleep(5)  # Wait between doses
            log_event('auto_ec', f'Low EC ({ec_val}) - dosed nutrients')

    def _check_plant_health(self):
        """Analyze plant health from images"""
        if not self.camera:
            return

        health_data = self.camera.analyze_plant_health()
        if not health_data:
            return

        threshold = self.config['triggers']['plant_health']['thresholds']['min_green_percent']

        if health_data['green_percentage'] < threshold:
            log_event('plant_health',
                      f"Low green coverage: {health_data['green_percentage']:.1f}% < {threshold}%")