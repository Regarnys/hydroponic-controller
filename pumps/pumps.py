# File: pumps/pumps.py
import time
import RPi.GPIO as GPIO

# Map each pump name to (enable_pin, input_pin)
pump_pins = {
    "pH_up":     (12, 4),
    "pH_down":   (13, 5),
    "nutrientA": (16, 6),
    "nutrientB": (19, 20),
    "nutrientC": (21, 26),
}

def init_pumps():
    """
    Set pin numbering mode & initialize all pump pins.
    Call once, e.g., in app.py.
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pump_name, (en_pin, in_pin) in pump_pins.items():
        GPIO.setup(en_pin, GPIO.OUT)
        GPIO.setup(in_pin, GPIO.OUT)
        GPIO.output(en_pin, GPIO.LOW)
        GPIO.output(in_pin, GPIO.LOW)

def pump_on(pump_name):
    en_pin, in_pin = pump_pins[pump_name]
    GPIO.output(in_pin, GPIO.HIGH)
    GPIO.output(en_pin, GPIO.HIGH)

def pump_off(pump_name):
    en_pin, in_pin = pump_pins[pump_name]
    GPIO.output(in_pin, GPIO.LOW)
    GPIO.output(en_pin, GPIO.LOW)

def dose_pump(pump_name, seconds):
    """
    Run pump_name for 'seconds' seconds (blocking).
    """
    pump_on(pump_name)
    time.sleep(seconds)
    pump_off(pump_name)
