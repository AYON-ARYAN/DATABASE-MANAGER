"""
Groq API key pool with automatic round-robin rotation.

Loads GROQ_API_KEY_1 … GROQ_API_KEY_6 from the environment.
Falls back to the legacy GROQ_API_KEY if no indexed keys are found.

Rotation policy:
  When a key returns HTTP 429 (rate limit / quota exhausted), call rotate().
  Keys cycle: 1 → 2 → 3 → 4 → 5 → 6 → 1 → ...
  The state is in-memory and shared across all threads via a lock.
"""

import os
import threading

from dotenv import load_dotenv

load_dotenv()

_lock = threading.Lock()
_current_index = 0


def _load_keys() -> list:
    keys = []
    for i in range(1, 7):
        k = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    # Backward-compat: fall back to legacy single key
    if not keys:
        legacy = os.getenv("GROQ_API_KEY", "").strip()
        if legacy:
            keys.append(legacy)
    return keys


_keys = _load_keys()


def get_current_key():
    """Return the currently active Groq API key, or None if none configured."""
    with _lock:
        if not _keys:
            return None
        return _keys[_current_index % len(_keys)]


def rotate():
    """
    Advance to the next key in the pool (called after a 429 error).
    Returns the new active key.
    """
    global _current_index
    with _lock:
        if not _keys:
            return None
        _current_index = (_current_index + 1) % len(_keys)
        new_key = _keys[_current_index]
    print(f"[Groq] Rotated to key #{(_current_index % len(_keys)) + 1} of {len(_keys)}")
    return new_key


def key_count() -> int:
    return len(_keys)


def any_key_available() -> bool:
    return bool(_keys)
