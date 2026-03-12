"""
Snapshot Engine — Adapter-Aware
File-based snapshots for SQLite. No-op for remote databases.
"""

import os
import shutil
from datetime import datetime

DB_PATH = "db/main.db"
SNAP_DIR = "db/snapshots"
MAX_SNAPS = 3

os.makedirs(SNAP_DIR, exist_ok=True)


def take_snapshot(adapter=None):
    """
    Take a database snapshot.
    - SQLite: copies the .db file
    - Others: no-op (returns False)
    """
    if adapter is not None:
        if not adapter.supports_snapshot:
            return False
        db_path = adapter.config.get("db_path", DB_PATH)
    else:
        db_path = DB_PATH

    if not os.path.exists(db_path):
        return False

    snaps = sorted(os.listdir(SNAP_DIR))

    # Remove oldest if exceeding limit
    if len(snaps) >= MAX_SNAPS:
        os.remove(os.path.join(SNAP_DIR, snaps[0]))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_path = os.path.join(SNAP_DIR, f"{timestamp}.db")
    shutil.copy(db_path, snap_path)
    return True


def undo(steps=1, adapter=None):
    """
    Restore a previous snapshot.
    Only works for SQLite.
    """
    if adapter is not None:
        if not adapter.supports_snapshot:
            raise Exception("Undo is not available for remote databases. Only SQLite supports snapshots.")
        db_path = adapter.config.get("db_path", DB_PATH)
    else:
        db_path = DB_PATH

    snaps = sorted(os.listdir(SNAP_DIR), reverse=True)
    if steps > len(snaps):
        raise Exception("Undo state not available")

    restore_snap = snaps[steps - 1]
    shutil.copy(os.path.join(SNAP_DIR, restore_snap), db_path)


def has_snapshots() -> bool:
    """Check if there are any snapshots available."""
    return len(os.listdir(SNAP_DIR)) > 0
