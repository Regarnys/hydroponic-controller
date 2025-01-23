# File: app.py

from flask import Flask, render_template
import csv

app = Flask(__name__)


@app.route("/")
def index():
    # Make sure to define sensor_rows BEFORE using it
    sensor_rows = []

    with open("sensor_data.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip header
        for row in reader:
            sensor_rows.append(row)

    return render_template("index.html", sensor_data=sensor_rows)

@app.route("/events")
def events():
    event_rows = []
    with open("hydro_events.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # skip the header
        for row in reader:
            event_rows.append(row)
    
    return render_template("events.html", event_data=event_rows)

@app.route("/manual", methods=["GET", "POST"])
def manual_control():
    pump_names = ["pH_up", "pH_down", "nutrientA", "nutrientB", "nutrientC"]
    if request.method == "POST":
        selected_pump = request.form.get("pump_name")
        seconds_str = request.form.get("run_seconds")
        
        if selected_pump and seconds_str:
            # Convert input to float or int
            run_sec = float(seconds_str)
            
            # Actually call your pump logic
            dose_pump(selected_pump, run_sec)
            log_event("manual_dose", f"{selected_pump} for {run_sec}s")
            
            return redirect(url_for("manual_control"))
        else:
            # missing fields => just reload
            return redirect(url_for("manual_control"))
    
    # GET method => display the form
    return render_template("manual.html", pump_names=pump_names)


if __name__ == "__main__":
    # run Flask on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
