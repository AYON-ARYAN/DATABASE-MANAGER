"""
Snapshot Engine
Cross-database snapshot management via adapter methods.
Maintains a registry of snapshots in db/snapshots.json.
"""

import os
import json
import uuid
from datetime import datetime

SNAP_DIR = "db/snapshots"
REGISTRY_FILE = "db/snapshots.json"
MAX_SNAPS_PER_DB = 5

os.makedirs(SNAP_DIR, exist_ok=True)


def _load_registry() -> list:
    if not os.path.exists(REGISTRY_FILE):
        return []
    try:
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def _save_registry(registry: list):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def get_snapshot(snap_id: str):
    registry = _load_registry()
    for snap in registry:
        if snap["id"] == snap_id:
            return snap
    return None


def list_snapshots(connection_name=None) -> list:
    """List snapshots, optionally filtered by connection name. Sorted newest first."""
    registry = _load_registry()
    if connection_name:
        registry = [s for s in registry if s.get("connection_name") == connection_name]
    return sorted(registry, key=lambda x: x["timestamp"], reverse=True)


def delete_snapshot(snap_id: str) -> bool:
    registry = _load_registry()
    snap = None
    for i, s in enumerate(registry):
        if s["id"] == snap_id:
            snap = registry.pop(i)
            break

    if snap:
        if os.path.exists(snap["file_path"]):
            try:
                os.remove(snap["file_path"])
            except OSError:
                pass
        _save_registry(registry)
        return True
    return False


def take_snapshot(adapter, connection_name: str):
    """
    Take a database snapshot using the adapter.
    Returns the snapshot metadata dict on success, or None on failure.
    """
    if not adapter or not adapter.supports_snapshot:
        return None

    registry = _load_registry()

    # Enforce limit per connection
    conn_snaps = [s for s in registry if s.get("connection_name") == connection_name]
    conn_snaps = sorted(conn_snaps, key=lambda x: x["timestamp"]) # oldest first

    if len(conn_snaps) >= MAX_SNAPS_PER_DB:
        # Delete oldest
        delete_snapshot(conn_snaps[0]["id"])
        registry = _load_registry() # Reload after delete

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_id = str(uuid.uuid4())[:8]
    ext = "db" if adapter.dialect == "sqlite" else "dump"
    if adapter.dialect == "mongodb":
        ext = "gz"

    filename = f"{connection_name}_{timestamp}_{snap_id}.{ext}"
    # Sanitizing filename just in case
    filename = filename.replace(" ", "_").replace("/", "-")
    filepath = os.path.join(SNAP_DIR, filename)

    success = adapter.take_snapshot(filepath)
    if success:
        snap = {
            "id": snap_id,
            "connection_name": connection_name,
            "db_type": adapter.dialect,
            "timestamp": datetime.now().isoformat(),
            "formatted_time": datetime.now().strftime("%b %d, %Y - %H:%M:%S"),
            "file_path": filepath
        }
        registry.append(snap)
        _save_registry(registry)
        return snap
    return None


def restore_snapshot(snap_id: str, adapter) -> bool:
    """
    Restore a specific snapshot.
    """
    snap = get_snapshot(snap_id)
    if not snap:
        raise ValueError("Snapshot not found.")

    if not adapter or not adapter.supports_snapshot:
        raise ValueError("Adapter does not support snapshots.")

    return adapter.restore_snapshot(snap["file_path"])


def undo(steps=1, adapter=None, connection_name="Default SQLite"):
    """
    Backwards compatibility: Restore the (steps)th most recent snapshot for the active DB.
    """
    snaps = list_snapshots(connection_name)
    if not snaps:
        raise Exception("No snapshots available to undo.")
        
    if steps > len(snaps):
        raise Exception("Undo state not available.")

    target_snap = snaps[steps - 1]
    success = restore_snapshot(target_snap["id"], adapter)
    if not success:
         raise Exception("Failed to restore snapshot.")


def has_snapshots(connection_name=None) -> bool:
    """Check if there are any snapshots available."""
    return len(list_snapshots(connection_name)) > 0
