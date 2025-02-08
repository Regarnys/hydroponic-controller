#!/usr/bin/env python3
from flask import Blueprint, render_template
import csv
import os
from datetime import datetime

events_bp = Blueprint('events', __name__, template_folder='../templates')

def aggregate_event_data():
    events_csv = os.path.join(os.path.dirname(__file__), "../data/hydro_events.csv")
    aggregator = {}
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                ts_str, pump, usage_str = row[:3]
                try:
                    usage = float(usage_str)
                    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    continue
                aggregator.setdefault(date_str, {})
                aggregator[date_str][pump] = aggregator[date_str].get(pump, 0) + usage
    return aggregator

@events_bp.route("/")
def events_dashboard():
    aggregator = aggregate_event_data()
    return render_template("events.html", summary=aggregator)
