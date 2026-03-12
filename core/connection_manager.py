"""
Connection Manager
Handles saving, loading, testing, and switching database connections.
Credentials are stored encrypted in db/connections.json.
"""

import os
import json
import base64
from cryptography.fernet import Fernet

from core.adapters import get_adapter, DB_TYPES

# ---------------------------------------------------
# Paths
# ---------------------------------------------------
CONN_FILE = "db/connections.json"
KEY_FILE = "db/.secret_key"


# ---------------------------------------------------
# Encryption helpers
# ---------------------------------------------------
def _get_key():
    """Load or generate a Fernet encryption key."""
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    with open(KEY_FILE, "wb") as f:
        f.write(key)
    return key


def _encrypt(text: str) -> str:
    if not text:
        return ""
    f = Fernet(_get_key())
    return f.encrypt(text.encode()).decode()


def _decrypt(token: str) -> str:
    if not token:
        return ""
    f = Fernet(_get_key())
    return f.decrypt(token.encode()).decode()


# ---------------------------------------------------
# Storage
# ---------------------------------------------------
def _load_connections() -> dict:
    if not os.path.exists(CONN_FILE):
        return {}
    with open(CONN_FILE, "r") as f:
        return json.load(f)


def _save_connections(data: dict):
    os.makedirs(os.path.dirname(CONN_FILE), exist_ok=True)
    with open(CONN_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------
# Public API
# ---------------------------------------------------
def list_connections() -> list:
    """
    Returns list of dicts:
    [{"name": "...", "db_type": "...", "config": {...}}, ...]
    Passwords are MASKED for display.
    """
    conns = _load_connections()
    result = []
    for name, info in conns.items():
        config_display = dict(info.get("config", {}))
        # Mask password for display
        if "password" in config_display and config_display["password"]:
            config_display["password"] = "••••••••"
        result.append({
            "name": name,
            "db_type": info.get("db_type", "sqlite"),
            "config": config_display,
        })
    return result


def add_connection(name: str, db_type: str, config: dict) -> dict:
    """
    Save a new connection. Passwords are encrypted.
    Returns {"success": True/False, "message": "..."}
    """
    if db_type not in DB_TYPES:
        return {"success": False, "message": f"Unsupported database type: {db_type}"}

    if not name or not name.strip():
        return {"success": False, "message": "Connection name is required."}

    conns = _load_connections()

    # Encrypt password
    encrypted_config = dict(config)
    if "password" in encrypted_config and encrypted_config["password"]:
        encrypted_config["password"] = _encrypt(encrypted_config["password"])

    conns[name.strip()] = {
        "db_type": db_type,
        "config": encrypted_config,
    }
    _save_connections(conns)
    return {"success": True, "message": f"Connection '{name}' saved."}


def delete_connection(name: str) -> dict:
    conns = _load_connections()
    if name not in conns:
        return {"success": False, "message": f"Connection '{name}' not found."}
    del conns[name]
    _save_connections(conns)
    return {"success": True, "message": f"Connection '{name}' deleted."}


def get_adapter_for_connection(name: str):
    """
    Returns an instantiated adapter for the named connection.
    Decrypts the password before passing config to the adapter.
    """
    conns = _load_connections()
    if name not in conns:
        raise ValueError(f"Connection '{name}' not found.")

    info = conns[name]
    db_type = info["db_type"]
    config = dict(info["config"])

    # Decrypt password
    if "password" in config and config["password"]:
        try:
            config["password"] = _decrypt(config["password"])
        except Exception:
            pass  # Already plaintext or corrupted

    adapter_cls = get_adapter(db_type)
    return adapter_cls(config)


def test_connection(name: str) -> dict:
    """Test if a saved connection works."""
    try:
        adapter = get_adapter_for_connection(name)
        ok = adapter.test_connection()
        if ok:
            return {"success": True, "message": f"✅ Connection '{name}' is working."}
        else:
            return {"success": False, "message": f"❌ Connection '{name}' failed."}
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"}


def test_new_connection(db_type: str, config: dict) -> dict:
    """Test a connection before saving it."""
    try:
        adapter_cls = get_adapter(db_type)
        adapter = adapter_cls(config)
        ok = adapter.test_connection()
        if ok:
            return {"success": True, "message": "✅ Connection successful!"}
        else:
            return {"success": False, "message": "❌ Connection failed."}
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"}


def ensure_default_sqlite():
    """
    Ensure the default SQLite connection exists.
    Called on app startup.
    """
    conns = _load_connections()
    if "Default SQLite" not in conns:
        conns["Default SQLite"] = {
            "db_type": "sqlite",
            "config": {"db_path": "db/main.db"},
        }
        _save_connections(conns)
