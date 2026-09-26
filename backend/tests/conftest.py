"""Shared test fixtures."""
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

# Point at a temp DB and storage dir for all tests
@pytest.fixture(autouse=True, scope="session")
def isolated_settings(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("reel2short_test")
    db_path = tmp / "test.db"
    storage = tmp / "storage"

    with patch.dict(os.environ, {
        "DATABASE_URL": f"sqlite:///{db_path}",
        "STORAGE_DIR": str(storage),
        "FFMPEG_PATH": "ffmpeg",
        "FFPROBE_PATH": "ffprobe",
        "REDIS_URL": "redis://localhost:6379/1",  # DB 1 for tests
    }):
        # Re-import settings so it picks up the patched env
        import importlib
        import app.config as config_module
        importlib.reload(config_module)

        from app.database import init_db, engine, Base
        # Reimport models so they register with new engine
        import app.models.video_asset  # noqa
        import app.models.processing_job  # noqa
        Base.metadata.create_all(bind=engine)

        config_module.settings.ensure_dirs()
        yield config_module.settings


@pytest.fixture()
def db_session(isolated_settings):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def sample_video(tmp_path) -> Path:
    """
    Use the existing instagram_reel.mp4 from the project root for integration tests.
    Falls back to a tiny synthetic MP4 header if not available.
    """
    real = Path(__file__).parent.parent.parent / "instagram_reel.mp4"
    if real.exists():
        return real

    # Minimal valid MP4 (ftyp box only — enough for path/size tests)
    mp4_bytes = bytes.fromhex(
        "0000001c667479706d703432"  # ftyp mp42
        "0000000000000000"
        "6d703432"
    )
    p = tmp_path / "test_video.mp4"
    p.write_bytes(mp4_bytes)
    return p

