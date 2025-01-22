# File: test_dosing_logic.py

import time

# We'll import your dosing logic from the real module
from controller.dosing_logic import simple_ph_control, simple_ec_control


# We'll mock out pumps by just printing or returning a change in the simulation
# Instead of actually calling dose_pump from pumps.pumps
def mock_dose_pump(pump_name, seconds, sim):
    """
    Instead of physically turning on a pump,
    adjust the simulation's pH/EC depending on the pump_name.
    'sim' is our simulated reservoir state.
    """
    # Just print a message for clarity
    print(f"[MOCK PUMP] {pump_name} for {seconds}s")

    # Adjust the sim state
    if pump_name == "pH_up":
        # pH_up might raise pH by 0.1 per second, for example
        sim["pH"] += 0.1 * seconds
    elif pump_name == "pH_down":
        # might lower pH by 0.1 per second
        sim["pH"] -= 0.1 * seconds
    elif pump_name == "nutrientA":
        # might raise EC by 0.2 per second
        sim["EC"] += 0.2 * seconds
    elif pump_name == "nutrientB":
        sim["EC"] += 0.2 * seconds
    elif pump_name == "nutrientC":
        sim["EC"] += 0.2 * seconds

    # You could add more elaborate logic if you want synergy or diminishing returns


def run_simulated_test():
    # Create a simulated reservoir state
    sim_state = {
        "pH": 5.4,  # start too low
        "EC": 0.8,  # also below desired
    }

    # We'll run multiple loops to see the logic in action
    for cycle in range(1, 10):
        pH_val = sim_state["pH"]
        ec_val = sim_state["EC"]

        print(f"\n=== Cycle {cycle} ===")
        print(f"Current sim pH={pH_val:.2f}, EC={ec_val:.2f}")

        # 1. Use the logic to see if pH needs adjusting
        ph_status = simple_ph_control(pH_val)
        if "Dosed" in ph_status:
            # parse which pump and how many seconds from the logic
            # E.g. "pH=5.4 -> Dosed pH_up for 1s"
            # We'll parse out the last part
            # or you can modify 'simple_ph_control' to return structured data
            parts = ph_status.split()
            # e.g. ['pH=5.4', '->', 'Dosed', 'pH_up', 'for', '1s']
            pump_name = parts[3]
            sec_string = parts[5]  # '1s'
            seconds = float(sec_string.replace("s", ""))

            # Call the mock dosing function instead of real hardware
            mock_dose_pump(pump_name, seconds, sim_state)

        # 2. Use the logic to see if EC needs adjusting
        ec_status = simple_ec_control(ec_val)
        if "Dosed" in ec_status:
            parts = ec_status.split()
            # e.g. ['EC=0.8', '->', 'Dosed', 'nutrientA', 'for', '2s']
            pump_name = parts[3]
            sec_string = parts[5]
            seconds = float(sec_string.replace("s", ""))

            mock_dose_pump(pump_name, seconds, sim_state)

        # 3. Maybe simulate some time passing, stable environment
        #    We'll just do a short sleep so we can see output
        time.sleep(1)

        # Check if we reached desired range
        if 5.8 <= sim_state["pH"] <= 6.2 and sim_state["EC"] >= 1.0:
            print("Desired pH and EC reached! Test done.")
            break
    else:
        print("Didn't reach desired range within 10 cycles.")


if __name__ == "__main__":
    run_simulated_test()
