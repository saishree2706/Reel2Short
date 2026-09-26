"""Tests for video API endpoints: probe, convert, preview."""
import io
import uuid
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(isolated_settings):
    """FastAPI test client with isolated DB."""
    from app.main import app
    return TestClient(app)


@pytest.fixture()
def stored_asset(db_session, sample_video) -> str:
    """Create a VideoAsset pointing to the real sample video."""
    from app.models.video_asset import VideoAsset
    asset = VideoAsset(
        id=str(uuid.uuid4()),
        source="manual",
        file_path=str(sample_video),
        original_filename=sample_video.name,
        mime_type="video/mp4",
        file_size=sample_video.stat().st_size,
    )
    db_session.add(asset)
    db_session.commit()
    return asset.id


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_200_and_valid_schema(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "environment" in data
        assert "python_version" in data
        assert "platform" in data
        assert "storage_dir" in data
        assert "instagram_configured" in data
        assert Path(data["storage_dir"]).exists()


# ---------------------------------------------------------------------------
# Probe endpoint
# ---------------------------------------------------------------------------

class TestProbeEndpoint:

    def test_probe_valid_video(self, client, stored_asset):
        resp = client.get(f"/api/videos/{stored_asset}/probe")
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_id"] == stored_asset
        assert data["aspect_ratio"] in ("vertical", "square", "horizontal", "unknown")
        # Real video should have dimensions
        assert data["width"] is not None

    def test_probe_not_found(self, client):
        resp = client.get("/api/videos/nonexistent-id/probe")
        assert resp.status_code == 404

    def test_probe_missing_file(self, client, db_session):
        from app.models.video_asset import VideoAsset
        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/nonexistent/path/video.mp4",
            original_filename="missing.mp4",
        )
        db_session.add(asset)
        db_session.commit()
        resp = client.get(f"/api/videos/{asset.id}/probe")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Convert endpoint
# ---------------------------------------------------------------------------

class TestConvertEndpoint:

    def test_invalid_mode_returns_422(self, client, stored_asset):
        resp = client.post(
            f"/api/videos/{stored_asset}/convert",
            json={"mode": "invalid_mode"},
        )
        assert resp.status_code == 422

    def test_asset_not_found_returns_404(self, client):
        with patch("app.services.queue_service.is_redis_available", return_value=True):
            resp = client.post(
                "/api/videos/no-such-asset/convert",
                json={"mode": "crop"},
            )
        assert resp.status_code == 404

    def test_redis_unavailable_returns_503(self, client, stored_asset):
        with patch("app.api.videos.is_redis_available", return_value=False):
            resp = client.post(
                f"/api/videos/{stored_asset}/convert",
                json={"mode": "crop"},
            )
        assert resp.status_code == 503

    def test_create_crop_job(self, client, stored_asset):
        mock_rq = MagicMock()
        mock_rq.id = "rq-test-123"
        with patch("app.api.videos.is_redis_available", return_value=True):
            with patch("app.services.queue_service.get_redis_connection"):
                with patch("rq.Queue.enqueue", return_value=mock_rq):
                    resp = client.post(
                        f"/api/videos/{stored_asset}/convert",
                        json={"mode": "crop"},
                    )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "queued"
        assert data["conversion_mode"] == "crop"
        assert data["video_asset_id"] == stored_asset

    def test_create_blur_background_job(self, client, stored_asset):
        mock_rq = MagicMock()
        mock_rq.id = "rq-test-456"
        with patch("app.api.videos.is_redis_available", return_value=True):
            with patch("app.services.queue_service.get_redis_connection"):
                with patch("rq.Queue.enqueue", return_value=mock_rq):
                    resp = client.post(
                        f"/api/videos/{stored_asset}/convert",
                        json={"mode": "blur_background"},
                    )
        assert resp.status_code == 202
        data = resp.json()
        assert data["conversion_mode"] == "blur_background"


# ---------------------------------------------------------------------------
# Job status endpoint
# ---------------------------------------------------------------------------

class TestJobStatusEndpoint:

    def test_job_not_found(self, client):
        resp = client.get("/api/jobs/nonexistent-job-id")
        assert resp.status_code == 404

    def test_job_queued_status(self, client, db_session, stored_asset):
        from app.services.job_service import JobService
        job = JobService.create_job(db_session, stored_asset, "crop")
        resp = client.get(f"/api/jobs/{job.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    def test_job_result_not_ready(self, client, db_session, stored_asset):
        from app.services.job_service import JobService
        job = JobService.create_job(db_session, stored_asset, "crop")
        resp = client.get(f"/api/jobs/{job.id}/result")
        assert resp.status_code == 409  # not completed yet

    def test_job_result_when_completed(self, client, db_session, stored_asset, sample_video):
        from app.services.job_service import JobService
        from app.models.video_asset import VideoAsset

        # Create output asset
        output = VideoAsset(
            id=str(uuid.uuid4()),
            source="converted",
            file_path=str(sample_video),
            original_filename="converted.mp4",
        )
        db_session.add(output)
        db_session.commit()

        job = JobService.create_job(db_session, stored_asset, "crop")
        JobService.mark_processing(db_session, job)
        JobService.mark_completed(db_session, job, output_asset_id=output.id)

        resp = client.get(f"/api/jobs/{job.id}/result")
        assert resp.status_code == 200
        assert resp.json()["id"] == output.id


# ---------------------------------------------------------------------------
# Preview / streaming endpoint
# ---------------------------------------------------------------------------

class TestPreviewEndpoint:

    def test_preview_returns_video(self, client, stored_asset):
        resp = client.get(f"/api/videos/{stored_asset}/preview")
        assert resp.status_code == 200
        assert "video" in resp.headers["content-type"]

    def test_preview_not_found(self, client):
        resp = client.get("/api/videos/no-such-id/preview")
        assert resp.status_code == 404

    def test_file_endpoint_also_streams(self, client, stored_asset):
        resp = client.get(f"/api/videos/{stored_asset}/file")
        assert resp.status_code == 200

    def test_range_request(self, client, stored_asset):
        """Partial content request returns 206 with correct headers."""
        resp = client.get(
            f"/api/videos/{stored_asset}/preview",
            headers={"Range": "bytes=0-1023"},
        )
        assert resp.status_code == 206
        assert "Content-Range" in resp.headers


# ---------------------------------------------------------------------------
# Worker task (integration with real FFmpeg, mocked DB)
# ---------------------------------------------------------------------------

class TestWorkerTask:

    def test_process_job_crop(self, db_session, sample_video, isolated_settings):
        """End-to-end: worker processes a crop job using real FFmpeg."""
        from app.models.video_asset import VideoAsset
        from app.models.processing_job import ProcessingJob
        from app.services.job_service import JobService
        from app.worker.tasks import process_job

        # Create source asset
        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="instagram",
            file_path=str(sample_video),
            original_filename=sample_video.name,
            mime_type="video/mp4",
        )
        db_session.add(asset)
        db_session.commit()

        # Create job
        job = JobService.create_job(db_session, asset.id, "crop")
        asset_id = asset.id  # capture before closing
        job_id = job.id
        db_session.close()  # worker opens its own session

        result = process_job(job_id)
        assert result["status"] == "completed"
        output_id = result["output_asset_id"]

        # Verify in DB
        from app.database import SessionLocal
        fresh_db = SessionLocal()
        try:
            fresh_job = fresh_db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            assert fresh_job.status == "completed"
            assert fresh_job.output_asset_id == output_id

            output_asset = fresh_db.query(VideoAsset).filter(VideoAsset.id == output_id).first()
            assert output_asset is not None
            assert output_asset.parent_asset_id == asset_id
            assert output_asset.conversion_mode == "crop"
            assert output_asset.width == 1080
            assert output_asset.height == 1920
        finally:
            fresh_db.close()

    def test_process_job_blur_background(self, db_session, sample_video):
        """End-to-end: worker processes a blur_background job."""
        from app.models.video_asset import VideoAsset
        from app.services.job_service import JobService
        from app.worker.tasks import process_job

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="instagram",
            file_path=str(sample_video),
            original_filename=sample_video.name,
        )
        db_session.add(asset)
        db_session.commit()

        job = JobService.create_job(db_session, asset.id, "blur_background")
        db_session.close()

        result = process_job(job.id)
        assert result["status"] == "completed"

    def test_process_job_missing_asset(self, db_session):
        """Worker job with non-existent asset → marked failed."""
        from app.models.video_asset import VideoAsset
        from app.models.processing_job import ProcessingJob
        from app.services.job_service import JobService
        from app.worker.tasks import process_job

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/totally/nonexistent/file.mp4",
            original_filename="ghost.mp4",
        )
        db_session.add(asset)
        db_session.commit()

        job = JobService.create_job(db_session, asset.id, "crop")
        db_session.close()

        with pytest.raises(Exception):
            process_job(job.id)

        from app.database import SessionLocal
        fresh_db = SessionLocal()
        try:
            fresh_job = fresh_db.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
            assert fresh_job.status == "failed"
            assert fresh_job.error_message
        finally:
            fresh_db.close()

    def test_process_job_invalid_mode(self, db_session, sample_video):
        """Worker rejects unknown conversion mode."""
        from app.models.video_asset import VideoAsset
        from app.models.processing_job import ProcessingJob
        from app.services.job_service import JobService
        from app.worker.tasks import process_job

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path=str(sample_video),
            original_filename=sample_video.name,
        )
        db_session.add(asset)

        job = ProcessingJob(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            job_type="convert",
            conversion_mode="invalid_mode",
            status="queued",
        )
        db_session.add(job)
        db_session.commit()
        job_id = job.id  # capture before closing
        db_session.close()

        with pytest.raises(Exception):
            process_job(job_id)

        from app.database import SessionLocal
        fresh_db = SessionLocal()
        try:
            j = fresh_db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            assert j.status == "failed"
        finally:
            fresh_db.close()
