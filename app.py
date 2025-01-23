# File: app.py

from flask import Flask, render_template
import csv

app = Flask(__name__)


@app.route("/")
def index():
    # Read sensor_data.csv for demonstration
    sensor_rows = []
    with open("data/sensor_data.csv", "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)  # skip the header row: timestamp,sensor_name,value
        for row in reader:
            sensor_rows.append(row)
            # each row is like [timestamp, sensor_name, value]

    # We'll pass 'sensor_rows' to our template to display or chart
    return render_template("index.html", sensor_data=sensor_rows)


if __name__ == "__main__":
    # run Flask on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
