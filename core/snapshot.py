import os
import shutil
from datetime import datetime

DB_PATH = "db/main.db"
SNAP_DIR = "db/snapshots"
MAX_SNAPS = 3

os.makedirs(SNAP_DIR, exist_ok=True)

def take_snapshot():
    snaps = sorted(os.listdir(SNAP_DIR))
    
    # Remove oldest if exceeding limit
    if len(snaps) >= MAX_SNAPS:
        os.remove(os.path.join(SNAP_DIR, snaps[0]))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_path = os.path.join(SNAP_DIR, f"{timestamp}.db")
    shutil.copy(DB_PATH, snap_path)

def undo(steps=1):
    snaps = sorted(os.listdir(SNAP_DIR), reverse=True)
    if steps > len(snaps):
        raise Exception("Undo state not available")

    restore_snap = snaps[steps - 1]
    shutil.copy(os.path.join(SNAP_DIR, restore_snap), DB_PATH)
