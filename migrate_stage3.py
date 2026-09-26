"""
Database migration for Stage 3.
Adds youtube_credentials and youtube_uploads tables.
Safe to run multiple times.
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DB_PATH = ROOT / "reel2short.db"

print(f"Migrating: {DB_PATH}")

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()


def table_exists(name: str) -> bool:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    )
    return cur.fetchone() is not None


# --- youtube_credentials ---
if not table_exists("youtube_credentials"):
    cur.execute("""
    CREATE TABLE youtube_credentials (
        id TEXT PRIMARY KEY,
        provider TEXT NOT NULL DEFAULT 'google',
        channel_id TEXT,
        channel_name TEXT,
        access_token TEXT,
        refresh_token TEXT,
        token_expiry TEXT,
        scopes TEXT,
        state TEXT NOT NULL DEFAULT 'active',
        created_at DATETIME,
        updated_at DATETIME
    )
    """)
    print("  Created youtube_credentials table")
else:
    print("  youtube_credentials already exists")

# --- youtube_uploads ---
if not table_exists("youtube_uploads"):
    cur.execute("""
    CREATE TABLE youtube_uploads (
        id TEXT PRIMARY KEY,
        video_asset_id TEXT NOT NULL,
        job_id TEXT,
        title TEXT NOT NULL,
        description TEXT,
        tags TEXT,
        privacy TEXT NOT NULL DEFAULT 'private',
        category_id TEXT,
        youtube_video_id TEXT,
        youtube_url TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        bytes_uploaded INTEGER,
        total_bytes INTEGER,
        error_message TEXT,
        upload_confirmed TEXT NOT NULL DEFAULT 'false',
        created_at DATETIME,
        updated_at DATETIME,
        completed_at DATETIME
    )
    """)
    print("  Created youtube_uploads table")
else:
    print("  youtube_uploads already exists")

conn.commit()
conn.close()
print("Stage 3 migration complete.")

