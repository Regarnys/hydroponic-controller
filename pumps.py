# File: hydroponic-controller/pumps/pumps.py

import time
import RPi.GPIO as GPIO

# Example: a dict that maps pump names to their (enable_pin, input_pin).
# Replace these with your own pins!
pump_pins = {
    "pH_up":        (12, 4),
    "pH_down":      (13, 5),
    "nutrientA":    (16, 6),
    "nutrientB":    (19, 20),
    "nutrientC":    (21, 26),
}


def init_pumps():
    """
    Sets up the GPIO pins for all defined pumps.
    Call this once at the start of your program.
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup each pump's pins as output, default LOW
    for pump_name, (en_pin, in_pin) in pump_pins.items():
        GPIO.setup(en_pin, GPIO.OUT)
        GPIO.setup(in_pin, GPIO.OUT)
        GPIO.output(en_pin, GPIO.LOW)
        GPIO.output(in_pin, GPIO.LOW)


def pump_on(pump_name):
    """
    Turn a single pump ON (enable=HIGH, input=HIGH).
    """
    en_pin, in_pin = pump_pins[pump_name]
    GPIO.output(in_pin, GPIO.HIGH)
    GPIO.output(en_pin, GPIO.HIGH)


def pump_off(pump_name):
    """
    Turn a single pump OFF (enable=LOW, input=LOW).
    """
    en_pin, in_pin = pump_pins[pump_name]
    GPIO.output(in_pin, GPIO.LOW)
    GPIO.output(en_pin, GPIO.LOW)


def dose_pump(pump_name, seconds):
    """
    Turn pump ON for 'seconds' duration, then OFF.
    This is a blocking call (sleeps).
    """
    pump_on(pump_name)
    time.sleep(seconds)
    pump_off(pump_name)
