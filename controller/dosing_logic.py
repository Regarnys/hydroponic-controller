# File: hydroponic-controller/controller/dosing_logic.py

from pumps.pumps import dose_pump


def simple_ph_control(pH):
    """
    Very naive logic:
    - If pH < 5.8, dose pH_up for 1 second.
    - If pH > 6.2, dose pH_down for 1 second.
    - Otherwise, do nothing.
    Return a status string for logging.
    """
    if pH < 5.8:
        dose_pump("pH_up", 1)
        return f"pH={pH} -> Dosed pH_up for 1s"
    elif pH > 6.2:
        dose_pump("pH_down", 1)
        return f"pH={pH} -> Dosed pH_down for 1s"
    else:
        return f"pH={pH} -> pH is in range, no action"


def simple_ec_control(ec):
    """
    Another naive example:
    - If EC < 1.0, dose nutrientA for 2 seconds
    - If we had multiple nutrients, we could do proportional or ratio-based dosing
    """
    if ec < 1.0:
        dose_pump("nutrientA", 2)
        return f"EC={ec} -> Dosed nutrientA for 2s"
    else:
        return f"EC={ec} -> EC is in range, no action"
