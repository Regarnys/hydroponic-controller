# File: sensors/ph_sensor.py
import random

def read_ph():
    """
    Mock reading a pH sensor. Replace with real code reading from an ADC or I2C sensor.
    """
    return round(random.uniform(5.5, 6.5), 2)
