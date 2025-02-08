#!/usr/bin/env python3
from flask import Blueprint, render_template, request
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
                ts_str, event, details = row[:3]
                try:
                    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    continue
                aggregator.setdefault(date_str, {})
                aggregator[date_str][event] = aggregator[date_str].get(event, 0) + 1
    return aggregator

@events_bp.route("/")
def events_dashboard():
    events_csv = os.path.join(os.path.dirname(__file__), "../data/hydro_events.csv")
    event_data = []
    if os.path.exists(events_csv):
        with open(events_csv, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            event_data = list(reader)
    return render_template("events.html", event_data=event_data)

@events_bp.route("/summary")
def events_summary():
    aggregated_data = []
    all_pumps = []
    aggregator = aggregate_event_data()
    for date, usage in aggregator.items():
        aggregated_data.append({"date": date, "usage": usage})
        for pump in usage.keys():
            if pump not in all_pumps:
                all_pumps.append(pump)
    return render_template("events_summary.html", aggregated_data=aggregated_data, all_pumps=all_pumps)
