"""
Database migration for Stage 4.
Adds scheduling columns to youtube_uploads table.
Safe to run multiple times.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DB_PATH = ROOT / "reel2short.db"

print(f"Migrating: {DB_PATH}")

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()


def column_exists(table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols


# Add scheduling columns to youtube_uploads
columns_to_add = [
    ("upload_mode", "TEXT NOT NULL DEFAULT 'upload_now'"),
    ("scheduled_at", "DATETIME"),
    ("scheduled_timezone", "TEXT"),
    ("publish_at", "TEXT"),   # ISO-8601 UTC string sent to YouTube
]

for col_name, col_def in columns_to_add:
    if not column_exists("youtube_uploads", col_name):
        cur.execute(f"ALTER TABLE youtube_uploads ADD COLUMN {col_name} {col_def}")
        print(f"  Added youtube_uploads.{col_name}")
    else:
        print(f"  youtube_uploads.{col_name} already exists")

conn.commit()
conn.close()
print("Stage 4 migration complete.")

