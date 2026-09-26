"""
Stage 3 tests: OAuth, token refresh, YouTube connection, upload validation,
upload jobs, storage lifecycle, cleanup.

Google/YouTube APIs are fully mocked — no real API quota consumed.
"""
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.youtube_credential import YouTubeCredential
from app.models.youtube_upload import YouTubeUpload
from app.models.video_asset import VideoAsset
from app.models.processing_job import ProcessingJob


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def test_db(tmp_path):
    """In-memory SQLite database for testing."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


@pytest.fixture(scope="function")
def client(test_db, tmp_path, monkeypatch):
    """TestClient with overridden DB dependency and isolated settings."""
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")

    def override_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_video(test_db, tmp_path):
    """A VideoAsset with a real (tiny) file on disk."""
    video_file = tmp_path / "test.mp4"
    video_file.write_bytes(b"\x00" * 1024)  # fake 1KB file
    asset = VideoAsset(
        id=str(uuid.uuid4()),
        source="manual",
        file_path=str(video_file),
        original_filename="test.mp4",
        mime_type="video/mp4",
        file_size=1024,
        width=1080,
        height=1920,
        aspect_ratio="vertical",
    )
    test_db.add(asset)
    test_db.commit()
    return asset


@pytest.fixture
def active_credential(test_db):
    """A connected YouTube credential."""
    cred = YouTubeCredential(
        id=str(uuid.uuid4()),
        provider="google",
        channel_id="UC_test123",
        channel_name="Test Channel",
        access_token="fake-access-token",
        refresh_token="fake-refresh-token",
        token_expiry=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
        scopes="https://www.googleapis.com/auth/youtube.upload",
        state="active",
    )
    test_db.add(cred)
    test_db.commit()
    return cred


# ---------------------------------------------------------------------------
# OAuth tests
# ---------------------------------------------------------------------------

class TestOAuthStart:
    def test_connect_returns_auth_url(self, client):
        with patch("app.api.auth.build_authorization_url") as mock_build:
            mock_build.return_value = ("https://accounts.google.com/auth?...", "state123")
            resp = client.get("/api/auth/google/connect")
        assert resp.status_code == 200
        data = resp.json()
        assert "auth_url" in data
        assert data["auth_url"] == "https://accounts.google.com/auth?..."

    def test_connect_raises_if_no_credentials_configured(self, client, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
        with patch("app.api.auth.build_authorization_url") as mock_build:
            mock_build.side_effect = RuntimeError("GOOGLE_CLIENT_ID must be set")
            resp = client.get("/api/auth/google/connect")
        assert resp.status_code == 500


class TestOAuthCallback:
    def test_user_denial_redirects(self, client):
        resp = client.get(
            "/api/auth/google/callback?error=access_denied",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=access_denied" in resp.headers["location"]

    def test_missing_code_redirects_with_error(self, client):
        resp = client.get(
            "/api/auth/google/callback",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "error=missing_params" in resp.headers["location"]

    def test_state_mismatch_redirects_with_error(self, client):
        with patch("app.api.auth.handle_oauth_callback") as mock_cb:
            mock_cb.side_effect = ValueError("OAuth state mismatch")
            resp = client.get(
                "/api/auth/google/callback?code=abc123&state=wrong_state",
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "error=state_mismatch" in resp.headers["location"]

    def test_successful_callback_redirects_with_connected(self, client, test_db):
        from app.api import auth as auth_module
        auth_module._pending_oauth_states["current"] = "valid_state"

        with patch("app.api.auth.handle_oauth_callback") as mock_cb:
            mock_cred = MagicMock()
            mock_cred.channel_name = "Test Channel"
            mock_cb.return_value = mock_cred
            resp = client.get(
                "/api/auth/google/callback?code=real_code&state=valid_state",
                follow_redirects=False,
            )
        assert resp.status_code == 302
        assert "connected=1" in resp.headers["location"]


class TestConnectionStatus:
    def test_status_when_disconnected(self, client):
        resp = client.get("/api/auth/google/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert "access_token" not in data
        assert "refresh_token" not in data

    def test_status_when_connected(self, client, active_credential):
        resp = client.get("/api/auth/google/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["channel_name"] == "Test Channel"
        assert data["channel_id"] == "UC_test123"
        # Ensure tokens never appear
        assert "access_token" not in data
        assert "refresh_token" not in data


class TestDisconnect:
    def test_disconnect_when_connected(self, client, active_credential, test_db):
        with patch("app.api.auth.disconnect") as mock_disc:
            mock_disc.return_value = True
            resp = client.post("/api/auth/google/disconnect")
        assert resp.status_code == 200
        assert "disconnected" in resp.json()["message"].lower()

    def test_disconnect_when_not_connected(self, client):
        with patch("app.api.auth.disconnect") as mock_disc:
            mock_disc.return_value = False
            resp = client.post("/api/auth/google/disconnect")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Token refresh tests
# ---------------------------------------------------------------------------

class TestTokenRefresh:
    def test_valid_token_not_refreshed(self, test_db, active_credential):
        from app.services.youtube_auth_service import get_valid_google_credentials

        with patch("google.oauth2.credentials.Credentials") as MockCreds:
            mock_creds = MagicMock()
            mock_creds.expired = False
            mock_creds.expiry = datetime.utcnow() + timedelta(hours=1)
            mock_creds.token = "valid-token"
            mock_creds.refresh_token = "valid-refresh"
            MockCreds.return_value = mock_creds

            with patch("app.services.youtube_auth_service._is_near_expiry", return_value=False):
                creds = get_valid_google_credentials(test_db)
                # No refresh should happen
                assert creds is not None

    def test_expired_token_triggers_refresh(self, test_db, active_credential):
        from app.services.youtube_auth_service import get_valid_google_credentials

        with patch("app.services.youtube_auth_service._is_near_expiry", return_value=True):
            with patch("google.auth.transport.requests.Request"):
                mock_creds = MagicMock()
                mock_creds.token = "new-access-token"
                mock_creds.refresh_token = "new-refresh-token"
                mock_creds.expiry = datetime.utcnow() + timedelta(hours=1)
                mock_creds.expired = False
                mock_creds.scopes = ["https://www.googleapis.com/auth/youtube.upload"]

                with patch("google.oauth2.credentials.Credentials", return_value=mock_creds):
                    with patch.object(mock_creds, "refresh") as mock_refresh:
                        get_valid_google_credentials(test_db)
                        mock_refresh.assert_called_once()

    def test_refresh_failure_marks_expired(self, test_db, active_credential):
        from app.services.youtube_auth_service import get_valid_google_credentials

        with patch("app.services.youtube_auth_service._is_near_expiry", return_value=True):
            with patch("google.oauth2.credentials.Credentials") as MockCreds:
                mock_creds = MagicMock()
                mock_creds.refresh.side_effect = Exception("refresh failed")
                MockCreds.return_value = mock_creds

                with pytest.raises(RuntimeError, match="Token refresh failed"):
                    get_valid_google_credentials(test_db)

                test_db.refresh(active_credential)
                assert active_credential.state == "expired"

    def test_no_credential_raises(self, test_db):
        from app.services.youtube_auth_service import get_valid_google_credentials

        with pytest.raises(RuntimeError, match="No YouTube account connected"):
            get_valid_google_credentials(test_db)


# ---------------------------------------------------------------------------
# Upload validation tests
# ---------------------------------------------------------------------------

class TestUploadValidation:
    def test_no_youtube_connection(self, client, sample_video):
        resp = client.post("/api/youtube/upload", json={
            "video_asset_id": sample_video.id,
            "title": "Test Video",
            "privacy": "private",
        })
        assert resp.status_code == 403
        assert "YouTube account" in resp.json()["detail"]

    def test_missing_title(self, client, sample_video, active_credential):
        resp = client.post("/api/youtube/upload", json={
            "video_asset_id": sample_video.id,
            "title": "",
            "privacy": "private",
        })
        assert resp.status_code == 422

    def test_video_not_found(self, client, active_credential):
        with patch("app.api.youtube.is_redis_available", return_value=True):
            resp = client.post("/api/youtube/upload", json={
                "video_asset_id": "nonexistent-id",
                "title": "Test",
                "privacy": "private",
            })
        assert resp.status_code == 404

    def test_invalid_privacy(self, client, sample_video, active_credential):
        resp = client.post("/api/youtube/upload", json={
            "video_asset_id": sample_video.id,
            "title": "Test",
            "privacy": "secret",
        })
        assert resp.status_code == 422

    def test_duplicate_upload_rejected(self, client, sample_video, active_credential, test_db):
        # Create a confirmed upload
        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=sample_video.id,
            title="Already uploaded",
            privacy="private",
            status="completed",
            youtube_video_id="yt_abc123",
            upload_confirmed="true",
        )
        test_db.add(upload)
        test_db.commit()

        with patch("app.api.youtube.is_redis_available", return_value=True):
            resp = client.post("/api/youtube/upload", json={
                "video_asset_id": sample_video.id,
                "title": "Try again",
                "privacy": "private",
            })
        assert resp.status_code == 409
        assert "already" in resp.json()["detail"].lower()

    def test_redis_unavailable(self, client, sample_video, active_credential):
        with patch("app.api.youtube.is_redis_available", return_value=False):
            resp = client.post("/api/youtube/upload", json={
                "video_asset_id": sample_video.id,
                "title": "Test",
                "privacy": "private",
            })
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Upload job tests
# ---------------------------------------------------------------------------

class TestUploadJob:
    def test_upload_job_created_and_queued(self, client, sample_video, active_credential, test_db):
        with patch("app.api.youtube.is_redis_available", return_value=True):
            with patch("rq.Queue.enqueue") as mock_enqueue:
                mock_rq_job = MagicMock()
                mock_rq_job.id = "rq-job-1"
                mock_enqueue.return_value = mock_rq_job

                resp = client.post("/api/youtube/upload", json={
                    "video_asset_id": sample_video.id,
                    "title": "My Short",
                    "description": "Test description",
                    "tags": ["tag1", "tag2"],
                    "privacy": "private",
                    "category_id": "22",
                })

        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "queued"
        assert data["title"] == "My Short"
        assert data["privacy"] == "private"
        assert "access_token" not in data
        assert "refresh_token" not in data

    def test_get_upload_status(self, client, test_db, sample_video):
        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=sample_video.id,
            title="Test",
            privacy="private",
            status="uploading",
            bytes_uploaded=500,
            total_bytes=1024,
        )
        test_db.add(upload)
        test_db.commit()

        resp = client.get(f"/api/youtube/uploads/{upload.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "uploading"
        assert data["bytes_uploaded"] == 500
        assert data["total_bytes"] == 1024
        assert "access_token" not in data

    def test_get_upload_not_found(self, client):
        resp = client.get("/api/youtube/uploads/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Storage lifecycle tests
# ---------------------------------------------------------------------------

class TestStorageLifecycle:
    def test_files_deleted_after_confirmed_upload(self, test_db, tmp_path):
        from app.services.cleanup_service import CleanupService

        video_file = tmp_path / "upload.mp4"
        video_file.write_bytes(b"\x00" * 100)

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path=str(video_file),
            original_filename="upload.mp4",
            mime_type="video/mp4",
        )
        test_db.add(asset)
        test_db.commit()

        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            title="Test",
            privacy="private",
            status="completed",
            youtube_video_id="ytid123",
            upload_confirmed="true",
        )
        test_db.add(upload)
        test_db.commit()

        deleted = CleanupService.cleanup_after_successful_upload(test_db, upload)
        assert deleted == 1
        assert not video_file.exists()

    def test_original_and_converted_deleted(self, test_db, tmp_path):
        from app.services.cleanup_service import CleanupService

        orig_file = tmp_path / "original.mp4"
        conv_file = tmp_path / "converted.mp4"
        orig_file.write_bytes(b"\x00" * 100)
        conv_file.write_bytes(b"\x00" * 100)

        original = VideoAsset(
            id=str(uuid.uuid4()),
            source="instagram",
            file_path=str(orig_file),
            original_filename="original.mp4",
            mime_type="video/mp4",
        )
        test_db.add(original)
        test_db.flush()

        converted = VideoAsset(
            id=str(uuid.uuid4()),
            source="converted",
            file_path=str(conv_file),
            original_filename="converted.mp4",
            mime_type="video/mp4",
            parent_asset_id=original.id,
        )
        test_db.add(converted)
        test_db.commit()

        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=converted.id,
            title="Test",
            privacy="private",
            status="completed",
            youtube_video_id="ytid456",
            upload_confirmed="true",
        )
        test_db.add(upload)
        test_db.commit()

        deleted = CleanupService.cleanup_after_successful_upload(test_db, upload)
        assert deleted == 2
        assert not orig_file.exists()
        assert not conv_file.exists()

    def test_unconfirmed_upload_does_not_delete(self, test_db, tmp_path):
        from app.services.cleanup_service import CleanupService

        video_file = tmp_path / "keep.mp4"
        video_file.write_bytes(b"\x00" * 100)

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path=str(video_file),
            original_filename="keep.mp4",
            mime_type="video/mp4",
        )
        test_db.add(asset)

        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            title="Test",
            privacy="private",
            status="failed",
            upload_confirmed="false",  # Not confirmed
        )
        test_db.add(upload)
        test_db.commit()

        deleted = CleanupService.cleanup_after_successful_upload(test_db, upload)
        assert deleted == 0
        assert video_file.exists()  # File retained

    def test_expired_failed_files_cleaned(self, test_db, tmp_path, monkeypatch):
        from app.services.cleanup_service import CleanupService
        import app.config as config_module

        monkeypatch.setattr(config_module.settings, "TEMP_VIDEO_RETENTION_HOURS", 0)

        video_file = tmp_path / "expired.mp4"
        video_file.write_bytes(b"\x00" * 100)

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path=str(video_file),
            original_filename="expired.mp4",
            mime_type="video/mp4",
        )
        test_db.add(asset)
        test_db.flush()

        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            title="Test",
            privacy="private",
            status="failed",
            upload_confirmed="false",
            updated_at=old_time,
        )
        test_db.add(upload)
        test_db.commit()

        deleted = CleanupService.cleanup_expired_temp_files(test_db)
        assert deleted == 1
        assert not video_file.exists()

    def test_active_upload_files_not_cleaned(self, test_db, tmp_path, monkeypatch):
        from app.services.cleanup_service import CleanupService
        import app.config as config_module

        monkeypatch.setattr(config_module.settings, "TEMP_VIDEO_RETENTION_HOURS", 0)

        video_file = tmp_path / "active.mp4"
        video_file.write_bytes(b"\x00" * 100)

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path=str(video_file),
            original_filename="active.mp4",
            mime_type="video/mp4",
        )
        test_db.add(asset)
        test_db.flush()

        # Failed old upload...
        failed_upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            title="Failed",
            privacy="private",
            status="failed",
            upload_confirmed="false",
            updated_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        test_db.add(failed_upload)

        # ...but there's ALSO an active upload for the same asset
        active_upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            title="Active",
            privacy="private",
            status="uploading",
            upload_confirmed="false",
        )
        test_db.add(active_upload)
        test_db.commit()

        deleted = CleanupService.cleanup_expired_temp_files(test_db)
        assert deleted == 0
        assert video_file.exists()  # Should NOT be deleted


# ---------------------------------------------------------------------------
# Worker task tests (with mocked Google API)
# ---------------------------------------------------------------------------

class TestWorkerUploadTask:
    def test_process_youtube_upload_success(self, tmp_path):
        """Worker processes upload with mocked Google API."""
        from app.database import init_db, SessionLocal
        from app.worker.tasks import process_youtube_upload

        # Use isolated DB for this test
        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/worker_test.db"

        # Reload settings so the new DB URL is picked up
        from app import config as config_mod
        config_mod.settings._db_url_raw = f"sqlite:///{tmp_path}/worker_test.db"

        # Re-create engine with new URL
        from app import database as db_mod
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        new_engine = create_engine(
            config_mod.settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
        db_mod.engine = new_engine
        db_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)
        from app.database import Base
        Base.metadata.create_all(bind=new_engine)

        db = db_mod.SessionLocal()
        video_file = tmp_path / "upload.mp4"
        video_file.write_bytes(b"\x00" * 1024)

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path=str(video_file),
            original_filename="upload.mp4",
            mime_type="video/mp4",
        )
        db.add(asset)
        db.flush()

        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            title="Test Short",
            privacy="private",
            status="queued",
        )
        db.add(upload)
        db.commit()
        upload_id = upload.id
        db.close()

        with patch(
            "app.services.youtube_auth_service.get_valid_google_credentials",
            return_value=MagicMock(),
        ):
            with patch(
                "app.services.youtube_upload_service.YouTubeUploadService.perform_upload",
                return_value="yt_test_video_id",
            ):
                with patch(
                    "app.services.cleanup_service.CleanupService.cleanup_after_successful_upload",
                    return_value=1,
                ):
                    result = process_youtube_upload(upload_id)

        assert result["status"] == "completed"
        assert result["youtube_video_id"] == "yt_test_video_id"

    def test_process_youtube_upload_already_confirmed(self, tmp_path):
        """Worker skips upload when already confirmed — idempotency."""
        from app.database import init_db, SessionLocal
        from app.worker.tasks import process_youtube_upload

        import os
        os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/worker_idempotent.db"

        from app import config as config_mod, database as db_mod
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        config_mod.settings._db_url_raw = f"sqlite:///{tmp_path}/worker_idempotent.db"
        new_engine = create_engine(
            config_mod.settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
        )
        db_mod.engine = new_engine
        db_mod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=new_engine)
        from app.database import Base
        Base.metadata.create_all(bind=new_engine)

        db = db_mod.SessionLocal()
        video_file = tmp_path / "confirmed.mp4"
        video_file.write_bytes(b"\x00" * 100)

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path=str(video_file),
            original_filename="confirmed.mp4",
            mime_type="video/mp4",
        )
        db.add(asset)
        db.flush()

        upload = YouTubeUpload(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            title="Test",
            privacy="private",
            status="completed",
            youtube_video_id="existing_id",
            upload_confirmed="true",
        )
        db.add(upload)
        db.commit()
        upload_id = upload.id
        db.close()

        with patch(
            "app.services.youtube_upload_service.YouTubeUploadService.perform_upload"
        ) as mock_upload:
            result = process_youtube_upload(upload_id)
            mock_upload.assert_not_called()

        assert result["status"] == "completed"
        assert result["youtube_video_id"] == "existing_id"


# ---------------------------------------------------------------------------
# Categories endpoint
# ---------------------------------------------------------------------------

class TestYouTubeCategories:
    def test_categories_returned(self, client):
        resp = client.get("/api/youtube/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) > 0
        cat = data["categories"][0]
        assert "id" in cat
        assert "name" in cat
