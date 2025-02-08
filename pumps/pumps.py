#!/usr/bin/env python3
"""
Module: pumps.py
This module provides functionality to initialize and control pumps using Raspberry Pi GPIO.
"""

import time
import RPi.GPIO as GPIO

# Define pump GPIO pins as (enable_pin, input_pin)
pump_pins = {
    "pH_up":     (12, 4),
    "pH_down":   (13, 5),
    "nutrientA": (16, 6),
    "nutrientB": (19, 20),
    "nutrientC": (21, 26),
}

def init_pumps():
    """
    Initializes GPIO settings for all pumps.
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    for (en_pin, in_pin) in pump_pins.values():
        GPIO.setup(en_pin, GPIO.OUT)
        GPIO.setup(in_pin, GPIO.OUT)
        GPIO.output(en_pin, GPIO.LOW)
        GPIO.output(in_pin, GPIO.LOW)

def pump_on(pump_name):
    """
    Activates the specified pump.
    """
    en_pin, in_pin = pump_pins[pump_name]
    GPIO.output(in_pin, GPIO.HIGH)
    GPIO.output(en_pin, GPIO.HIGH)

def pump_off(pump_name):
    """
    Deactivates the specified pump.
    """
    en_pin, in_pin = pump_pins[pump_name]
    GPIO.output(in_pin, GPIO.LOW)
    GPIO.output(en_pin, GPIO.LOW)

def dose_pump(pump_name, seconds):
    """
    Turns on the specified pump for 'seconds' seconds, then turns it off.
    """
    pump_on(pump_name)
    time.sleep(seconds)
    pump_off(pump_name)

if __name__ == "__main__":
    print("Initializing pumps...")
    init_pumps()
    print("Dosing pump pH_up for 3 seconds...")
    dose_pump("pH_up", 3)
    print("Done.")
    GPIO.cleanup()

