import json
import os
import uuid
from datetime import datetime

DASHBOARDS_FILE = "db/dashboards.json"

def _load_dashboards():
    if not os.path.exists(DASHBOARDS_FILE):
        return {"dashboards": []}
    try:
        with open(DASHBOARDS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"dashboards": []}

def _save_dashboards(data):
    os.makedirs(os.path.dirname(DASHBOARDS_FILE), exist_ok=True)
    with open(DASHBOARDS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def list_dashboards():
    return _load_dashboards()["dashboards"]

def get_dashboard(dashboard_id):
    data = _load_dashboards()
    for d in data["dashboards"]:
        if d["id"] == dashboard_id:
            return d
    return None

def create_dashboard(name):
    data = _load_dashboards()
    new_dash = {
        "id": str(uuid.uuid4()),
        "name": name,
        "widgets": [],
        "created_at": datetime.now().isoformat()
    }
    data["dashboards"].append(new_dash)
    _save_dashboards(data)
    return new_dash

def delete_dashboard(dashboard_id):
    data = _load_dashboards()
    data["dashboards"] = [d for d in data["dashboards"] if d["id"] != dashboard_id]
    _save_dashboards(data)

def add_widget(dashboard_id, title, query, chart_type="table", db_name="Default SQLite"):
    data = _load_dashboards()
    for d in data["dashboards"]:
        if d["id"] == dashboard_id:
            widget = {
                "id": str(uuid.uuid4()),
                "title": title,
                "query": query,
                "chart_type": chart_type,
                "db_name": db_name,
                "created_at": datetime.now().isoformat()
            }
            d["widgets"].append(widget)
            _save_dashboards(data)
            return widget
    return None

def remove_widget(dashboard_id, widget_id):
    data = _load_dashboards()
    for d in data["dashboards"]:
        if d["id"] == dashboard_id:
            d["widgets"] = [w for w in d["widgets"] if w["id"] != widget_id]
            _save_dashboards(data)
            return True
    return False
