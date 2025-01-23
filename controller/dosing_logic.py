# File: hydroponic-controller/controller/dosing_logic.py

import time
import datetime
from pumps.pumps import dose_pump

# -----------------------------
# Daily Dosing Limits
# -----------------------------
# For each pump, how many seconds max per day?
MAX_DAILY_SECONDS = {
    "pH_up": 30,       # e.g. 30s total per day
    "pH_down": 30,
    "nutrientA": 60,
    "nutrientB": 60,
    "nutrientC": 60
}

# Track how many seconds have been dosed today
daily_dose_counters = {
    "pH_up": 0,
    "pH_down": 0,
    "nutrientA": 0,
    "nutrientB": 0,
    "nutrientC": 0
}

# Store the date we last reset counters
last_reset_date = None


def reset_daily_counters_if_new_day():
    """
    Reset the daily_dose_counters if we have moved to a new calendar day.
    Useful to allow fresh dosing each day.
    """
    global last_reset_date, daily_dose_counters

    today_str = datetime.date.today().isoformat()
    if last_reset_date != today_str:
        # Reset
        for pump in daily_dose_counters:
            daily_dose_counters[pump] = 0
        last_reset_date = today_str


def can_dose(pump_name, seconds):
    """
    Check if we have enough "budget" to run pump_name for 'seconds' more
    within today's limit. Returns True/False.
    """
    if pump_name not in MAX_DAILY_SECONDS:
        return False  # unknown pump, safer to say no
    if daily_dose_counters[pump_name] + seconds > MAX_DAILY_SECONDS[pump_name]:
        return False
    return True


def record_dose(pump_name, seconds):
    """Increment the daily counter after a successful dose."""
    daily_dose_counters[pump_name] += seconds


# -----------------------------
# pH Control Logic
# -----------------------------
def simple_ph_control(pH):
    """
    Very naive pH logic:
    - If pH < 5.8 => dose pH_up for 1s (if limit allows).
    - If pH > 6.2 => dose pH_down for 1s (if limit allows).
    - Otherwise, do nothing.
    Returns a string describing the action (or lack thereof).
    """
    # First, ensure daily counters are up to date
    reset_daily_counters_if_new_day()

    if pH < 5.8:
        pump_name = "pH_up"
        dose_sec = 1
        if can_dose(pump_name, dose_sec):
            dose_pump(pump_name, dose_sec)
            record_dose(pump_name, dose_sec)
            return f"pH={pH:.2f} -> Dosed {pump_name} for {dose_sec}s"
        else:
            return f"pH={pH:.2f} -> {pump_name} limit reached, no further dosing"
    elif pH > 6.2:
        pump_name = "pH_down"
        dose_sec = 1
        if can_dose(pump_name, dose_sec):
            dose_pump(pump_name, dose_sec)
            record_dose(pump_name, dose_sec)
            return f"pH={pH:.2f} -> Dosed {pump_name} for {dose_sec}s"
        else:
            return f"pH={pH:.2f} -> {pump_name} limit reached, no further dosing"
    else:
        return f"pH={pH:.2f} -> pH in range, no action"


# -----------------------------
# EC Control Logic
# -----------------------------
def simple_ec_control(ec):
    """
    Simple EC logic:
    - If ec < 1.0 => dose nutrientA for 2s (if limit allows).
    - Otherwise do nothing.
    Returns a string describing the action (or lack thereof).
    """
    reset_daily_counters_if_new_day()

    if ec < 1.0:
        pump_name = "nutrientA"
        dose_sec = 2
        if can_dose(pump_name, dose_sec):
            dose_pump(pump_name, dose_sec)
            record_dose(pump_name, dose_sec)
            return f"EC={ec:.2f} -> Dosed {pump_name} for {dose_sec}s"
        else:
            return f"EC={ec:.2f} -> {pump_name} limit reached, no further dosing"
    else:
        return f"EC={ec:.2f} -> EC in range, no action"
