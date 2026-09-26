"""Job service — CRUD for ProcessingJob records and stale-job recovery."""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models.processing_job import ProcessingJob
from ..config import settings


VALID_MODES: set[str] = {"crop", "blur_background"}


class JobService:

    @staticmethod
    def create_job(
        db: Session,
        video_asset_id: str,
        conversion_mode: str,
        job_type: str = "convert",
    ) -> ProcessingJob:
        job = ProcessingJob(
            video_asset_id=video_asset_id,
            job_type=job_type,
            conversion_mode=conversion_mode,
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_job(db: Session, job_id: str) -> Optional[ProcessingJob]:
        return db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

    @staticmethod
    def mark_processing(db: Session, job: ProcessingJob) -> ProcessingJob:
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_completed(
        db: Session, job: ProcessingJob, output_asset_id: str
    ) -> ProcessingJob:
        job.status = "completed"
        job.output_asset_id = output_asset_id
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_failed(
        db: Session, job: ProcessingJob, error: str
    ) -> ProcessingJob:
        job.status = "failed"
        job.error_message = error[:1000]  # cap length
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def recover_stale_jobs(db: Session) -> int:
        """
        Reset jobs stuck in 'processing' for longer than WORKER_STALE_JOB_TIMEOUT_SECONDS.
        Returns the number of jobs reset.
        """
        timeout = settings.WORKER_STALE_JOB_TIMEOUT_SECONDS
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout)

        stale = (
            db.query(ProcessingJob)
            .filter(
                ProcessingJob.status == "processing",
                ProcessingJob.started_at < cutoff,
            )
            .all()
        )
        for job in stale:
            job.status = "queued"
            job.started_at = None
            job.error_message = "Reset from stale processing state"
            retry = int(job.retry_count or "0") + 1
            job.retry_count = str(retry)

        if stale:
            db.commit()
        return len(stale)


job_service = JobService()
