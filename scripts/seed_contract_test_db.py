#!/usr/bin/env python3
"""Seeds db/main.db ("Default SQLite") with the minimal Album/Artist tables
examples_api's /api/query, /api/overview/query, and /api/join/* examples
need to get a real 200 instead of a 500 (table doesn't exist).

db/*.db is gitignored (real user data, not fixtures) — a fresh checkout (like
CI's) has none of it, unlike a local dev environment that's already installed
a sample database. Deterministic and offline (no network download of a real
sample DB like Chinook) so it's safe and fast to run before every contract
test run, locally or in CI. Idempotent: safe to run against a db/main.db that
already has these tables (e.g. from an installed Chinook sample) or none at
all.

Run: python scripts/seed_contract_test_db.py
"""
import os
import sqlite3

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "db", "main.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH)
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Artist (
            ArtistId INTEGER PRIMARY KEY,
            Name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Album (
            AlbumId INTEGER PRIMARY KEY,
            Title TEXT NOT NULL,
            ArtistId INTEGER NOT NULL REFERENCES Artist(ArtistId)
        )
    """)
    conn.execute("INSERT OR IGNORE INTO Artist (ArtistId, Name) VALUES (1, 'Metallica'), (2, 'Accept')")
    conn.execute("INSERT OR IGNORE INTO Album (AlbumId, Title, ArtistId) VALUES "
                 "(1, 'For Those About To Rock We Salute You', 1), (2, 'Balls to the Wall', 2)")
    conn.commit()
finally:
    conn.close()

print(f"Seeded {DB_PATH} with Artist/Album tables (2 rows each).")
