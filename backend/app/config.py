"""Application configuration loaded from .env"""
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# Project root: backend/app/config.py -> backend/app -> backend -> root
_ROOT = Path(__file__).parent.parent.parent.resolve()
load_dotenv(_ROOT / ".env")


class Settings:
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_HOST: str = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    _db_url_raw: str = os.getenv("DATABASE_URL", "sqlite:///./reel2short.db")

    INSTAGRAM_APP_ID: str = os.getenv("INSTAGRAM_APP_ID", "")
    INSTAGRAM_APP_SECRET: str = os.getenv("INSTAGRAM_APP_SECRET", "")
    INSTAGRAM_REDIRECT_URI: str = os.getenv(
        "INSTAGRAM_REDIRECT_URI",
        "http://localhost:8000/api/auth/instagram/callback",
    )
    INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/api/auth/google/callback",
    )

    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini")
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_MODEL: str = os.getenv("AI_MODEL", "")

    _storage_dir_raw: str = os.getenv("STORAGE_DIR", "./storage")

    # FFmpeg/ffprobe: prefer explicit env var, fall back to PATH discovery
    FFMPEG_PATH: str = os.getenv("FFMPEG_PATH", "ffmpeg")
    FFPROBE_PATH: str = os.getenv("FFPROBE_PATH", "ffprobe")

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Worker
    WORKER_STALE_JOB_TIMEOUT_SECONDS: int = int(
        os.getenv("WORKER_STALE_JOB_TIMEOUT_SECONDS", "300")
    )

    # Storage lifecycle (Stage 3)
    TEMP_VIDEO_RETENTION_HOURS: int = int(
        os.getenv("TEMP_VIDEO_RETENTION_HOURS", "24")
    )

    # Stage 4: AI + Scheduling
    # Default IANA timezone for the schedule UI
    DEFAULT_TIMEZONE: str = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")

    @property
    def DATABASE_URL(self) -> str:
        """Return an absolute SQLite URL anchored to the project root."""
        raw = self._db_url_raw
        if raw.startswith("sqlite:///./") or raw.startswith("sqlite:///.\\"):
            rel = raw[len("sqlite:///./"):]
            abs_path = (_ROOT / rel).as_posix()
            return f"sqlite:///{abs_path}"
        return raw

    @property
    def STORAGE_DIR(self) -> str:
        """Return the resolved storage directory path string."""
        return str(self.storage_path)

    @STORAGE_DIR.setter
    def STORAGE_DIR(self, value: str) -> None:
        self._storage_dir_raw = value

    @property
    def storage_path(self) -> Path:
        raw = self._storage_dir_raw
        p = Path(raw)
        if not p.is_absolute():
            p = _ROOT / p
        return p.resolve()

    @property
    def downloads_dir(self) -> Path:
        return self.storage_path / "downloads"

    @property
    def uploads_dir(self) -> Path:
        return self.storage_path / "uploads"

    @property
    def converted_dir(self) -> Path:
        return self.storage_path / "converted"

    @property
    def temp_dir(self) -> Path:
        return self.storage_path / "temp"

    def ensure_dirs(self) -> None:
        """Create storage directories if they don't exist."""
        for d in [
            self.storage_path,
            self.downloads_dir,
            self.uploads_dir,
            self.converted_dir,
            self.temp_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def resolve_ffmpeg(self) -> str:
        """Return the resolved path to ffmpeg binary."""
        return _resolve_binary("ffmpeg", self.FFMPEG_PATH)

    def resolve_ffprobe(self) -> str:
        """Return the resolved path to ffprobe binary."""
        return _resolve_binary("ffprobe", self.FFPROBE_PATH)


def _resolve_binary(name: str, configured: str) -> str:
    """
    Resolve a binary path:
    1. If the configured value is an absolute/relative path that exists, use it.
    2. Otherwise discover via PATH using shutil.which().
    3. On Windows, check common user download and install locations as fallback.
    Raises RuntimeError if not found.
    """
    import sys
    p = Path(configured)
    if p.is_absolute() or len(p.parts) > 1:
        if p.exists():
            return str(p)
        raise RuntimeError(
            f"'{name}' binary not found at configured path: {configured}"
        )
    found = shutil.which(configured) or shutil.which(name)
    if found:
        return found

    # Common Windows fallback locations
    if sys.platform == "win32":
        user_home = Path.home()
        candidates = [
            user_home / "Downloads",
            user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages",
            Path("C:/ffmpeg/bin"),
            Path("C:/Program Files/ffmpeg/bin"),
        ]
        for base in candidates:
            if base.exists():
                try:
                    for match in base.glob(f"**/{name}.exe"):
                        if match.is_file():
                            return str(match)
                except Exception:
                    pass

    raise RuntimeError(
        f"'{name}' binary not found. "
        f"Install FFmpeg and add it to PATH, or set {name.upper()}_PATH in .env."
    )


settings = Settings()
