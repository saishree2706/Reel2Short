"""
Database migration script for Stage 2.
Adds new columns to video_assets table and creates processing_jobs table.
Safe to run multiple times (checks for existing columns).
"""
import sqlite3
from pathlib import Path

# Resolve DB path same as config.py does
ROOT = Path(__file__).parent.resolve()
DB_PATH = ROOT / "reel2short.db"

print(f"Migrating: {DB_PATH}")

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# --- video_assets new columns ---
def column_exists(table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())

new_columns = [
    ("codec_name",       "TEXT"),
    ("fps",              "REAL"),
    ("has_audio",        "TEXT"),
    ("parent_asset_id",  "TEXT"),
    ("conversion_mode",  "TEXT"),
]

for col_name, col_type in new_columns:
    if not column_exists("video_assets", col_name):
        cur.execute(f"ALTER TABLE video_assets ADD COLUMN {col_name} {col_type}")
        print(f"  Added video_assets.{col_name}")
    else:
        print(f"  video_assets.{col_name} already exists")

# --- processing_jobs table ---
cur.execute("""
CREATE TABLE IF NOT EXISTS processing_jobs (
    id TEXT PRIMARY KEY,
    video_asset_id TEXT NOT NULL,
    job_type TEXT NOT NULL DEFAULT 'convert',
    conversion_mode TEXT,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL,
    error_message TEXT,
    output_asset_id TEXT,
    retry_count TEXT NOT NULL DEFAULT '0',
    created_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME
)
""")
print("  processing_jobs table: OK")

conn.commit()
conn.close()
print("Migration complete.")

