"""Tests for job service, job model, and queue service."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import uuid


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------

class TestJobService:

    def test_create_job(self, db_session):
        from app.services.job_service import JobService
        from app.models.video_asset import VideoAsset

        # Create a dummy asset first
        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/tmp/dummy.mp4",
            original_filename="dummy.mp4",
        )
        db_session.add(asset)
        db_session.commit()

        job = JobService.create_job(db_session, asset.id, "crop")
        assert job.id
        assert job.status == "queued"
        assert job.video_asset_id == asset.id
        assert job.conversion_mode == "crop"
        assert job.created_at is not None

    def test_mark_processing(self, db_session):
        from app.services.job_service import JobService
        from app.models.video_asset import VideoAsset

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/tmp/dummy.mp4",
            original_filename="dummy.mp4",
        )
        db_session.add(asset)
        db_session.commit()

        job = JobService.create_job(db_session, asset.id, "blur_background")
        JobService.mark_processing(db_session, job)
        assert job.status == "processing"
        assert job.started_at is not None

    def test_mark_completed(self, db_session):
        from app.services.job_service import JobService
        from app.models.video_asset import VideoAsset

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/tmp/dummy.mp4",
            original_filename="dummy.mp4",
        )
        db_session.add(asset)
        db_session.commit()

        output_id = str(uuid.uuid4())
        job = JobService.create_job(db_session, asset.id, "crop")
        JobService.mark_processing(db_session, job)
        JobService.mark_completed(db_session, job, output_asset_id=output_id)
        assert job.status == "completed"
        assert job.output_asset_id == output_id
        assert job.completed_at is not None

    def test_mark_failed(self, db_session):
        from app.services.job_service import JobService
        from app.models.video_asset import VideoAsset

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/tmp/dummy.mp4",
            original_filename="dummy.mp4",
        )
        db_session.add(asset)
        db_session.commit()

        job = JobService.create_job(db_session, asset.id, "crop")
        JobService.mark_failed(db_session, job, error="FFmpeg error")
        assert job.status == "failed"
        assert "FFmpeg error" in job.error_message

    def test_get_job_not_found(self, db_session):
        from app.services.job_service import JobService
        result = JobService.get_job(db_session, "nonexistent-id")
        assert result is None

    def test_recover_stale_jobs(self, db_session):
        from app.services.job_service import JobService
        from app.models.processing_job import ProcessingJob
        from app.models.video_asset import VideoAsset

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/tmp/dummy.mp4",
            original_filename="dummy.mp4",
        )
        db_session.add(asset)
        db_session.commit()

        # Clean up any leftover processing jobs from previous tests
        db_session.query(ProcessingJob).filter(ProcessingJob.status == "processing").delete()
        db_session.commit()

        # Create a stale processing job (started 10 minutes ago)
        job = ProcessingJob(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            status="processing",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(job)
        db_session.commit()

        recovered = JobService.recover_stale_jobs(db_session)
        assert recovered == 1
        db_session.refresh(job)
        assert job.status == "queued"
        assert job.started_at is None

    def test_no_stale_jobs_recently_started(self, db_session):
        from app.services.job_service import JobService
        from app.models.processing_job import ProcessingJob
        from app.models.video_asset import VideoAsset

        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="manual",
            file_path="/tmp/dummy.mp4",
            original_filename="dummy.mp4",
        )
        db_session.add(asset)
        db_session.commit()

        # Recently started — should NOT be recovered
        job = ProcessingJob(
            id=str(uuid.uuid4()),
            video_asset_id=asset.id,
            status="processing",
            started_at=datetime.now(timezone.utc) - timedelta(seconds=30),
        )
        db_session.add(job)
        db_session.commit()

        recovered = JobService.recover_stale_jobs(db_session)
        assert recovered == 0
        db_session.refresh(job)
        assert job.status == "processing"


# ---------------------------------------------------------------------------
# Queue service (mocked Redis)
# ---------------------------------------------------------------------------

class TestQueueService:

    def test_is_redis_available_when_down(self):
        from app.services.queue_service import is_redis_available
        with patch("app.services.queue_service.get_redis_connection") as mock_conn:
            mock_conn.return_value.ping.side_effect = Exception("Connection refused")
            assert is_redis_available() is False

    def test_is_redis_available_when_up(self):
        from app.services.queue_service import is_redis_available
        with patch("app.services.queue_service.get_redis_connection") as mock_conn:
            mock_conn.return_value.ping.return_value = True
            assert is_redis_available() is True

    def test_enqueue_job_calls_queue(self, db_session):
        from app.services.queue_service import enqueue_job
        mock_rq_job = MagicMock()
        mock_rq_job.id = "rq-job-123"

        with patch("app.services.queue_service.get_redis_connection"):
            with patch("rq.Queue.enqueue", return_value=mock_rq_job):
                result = enqueue_job("test-job-id")
                assert result == "rq-job-123"

