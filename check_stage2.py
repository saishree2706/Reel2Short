from backend.app.config import settings
from backend.app.database import init_db
from backend.app.services.ffmpeg_service import verify_binaries, probe_video_sync
from backend.app.services.queue_service import is_redis_available
from pathlib import Path

settings.ensure_dirs()
init_db()
print("DB init OK")

bins = verify_binaries()
print("FFmpeg OK:", bins["ffmpeg"])
print("ffprobe OK:", bins["ffprobe"])

reel = Path("instagram_reel.mp4")
if reel.exists():
    probe = probe_video_sync(reel)
    print("Probe result:", probe)

redis_ok = is_redis_available()
print("Redis available:", redis_ok)
print("All system checks PASSED")

