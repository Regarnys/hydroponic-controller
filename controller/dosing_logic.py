# File: controller/dosing_logic.py
import time
import datetime
from pumps.pumps import dose_pump

# Suppose we do daily max of 30s each for pH_up/down, 60s for nutrients
MAX_DAILY_SECONDS = {
    "pH_up": 30,
    "pH_down": 30,
    "nutrientA": 60,
    "nutrientB": 60,
    "nutrientC": 60
}

daily_counters = {
    "pH_up": 0,
    "pH_down": 0,
    "nutrientA": 0,
    "nutrientB": 0,
    "nutrientC": 0
}

last_reset_date = None

def reset_if_new_day():
    global last_reset_date, daily_counters
    today = datetime.date.today().isoformat()
    if last_reset_date != today:
        for p in daily_counters:
            daily_counters[p] = 0
        last_reset_date = today

def can_dose(pump_name, seconds):
    if pump_name not in MAX_DAILY_SECONDS:
        return False
    return (daily_counters[pump_name] + seconds) <= MAX_DAILY_SECONDS[pump_name]

def record_dose(pump_name, seconds):
    daily_counters[pump_name] += seconds

def simple_ph_control(pH, ph_min=5.8, ph_max=6.2):
    """
    If pH < ph_min => dose pH_up for 1s
    If pH > ph_max => dose pH_down for 1s
    Otherwise no action
    """
    reset_if_new_day()

    if pH < ph_min:
        if can_dose("pH_up", 1):
            dose_pump("pH_up", 1)
            record_dose("pH_up", 1)
            return f"pH={pH} => Dosed pH_up 1s"
        else:
            return f"pH={pH} => limit reached for pH_up"
    elif pH > ph_max:
        if can_dose("pH_down", 1):
            dose_pump("pH_down", 1)
            record_dose("pH_down", 1)
            return f"pH={pH} => Dosed pH_down 1s"
        else:
            return f"pH={pH} => limit reached for pH_down"
    else:
        return f"pH={pH} => in range, no action"

def simple_ec_control(ec, ec_min=1.0):
    """
    If ec < ec_min => dose nutrientA for 2s
    Otherwise no action
    """
    reset_if_new_day()

    if ec < ec_min:
        if can_dose("nutrientA", 2):
            dose_pump("nutrientA", 2)
            record_dose("nutrientA", 2)
            return f"EC={ec} => Dosed nutrientA 2s"
        else:
            return f"EC={ec} => limit reached for nutrientA"
    else:
        return f"EC={ec} => in range, no action"

