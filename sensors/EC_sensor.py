# File: sensors/ec_sensor.py

import random

def read_ec():
    """
    Mock function for testing.
    Replace with real sensor code or library calls.
    Return a float representing the EC (mS/cm or another unit).
    """
    # Return a random value in a typical range, e.g. 0.8 to 1.8 mS/cm
    return round(random.uniform(0.8, 1.8), 2)
