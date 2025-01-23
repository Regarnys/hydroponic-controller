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


if __name__ == "__main__":
    # run Flask on port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)
