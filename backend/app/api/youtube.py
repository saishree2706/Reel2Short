"""
YouTube upload, scheduling, and management API endpoints.

Routes:
  GET  /api/youtube/categories
  GET  /api/youtube/timezone-config
  POST /api/youtube/upload              — create upload or schedule job
  GET  /api/youtube/uploads/{id}        — get upload status
  GET  /api/youtube/uploads             — list uploads
  POST /api/youtube/uploads/{id}/reschedule   — change scheduled time
  POST /api/youtube/uploads/{id}/cancel-schedule  — cancel schedule → private
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.youtube import (
    RescheduleRequest,
    TimezoneConfig,
    YouTubeUploadRequest,
    YouTubeUploadResponse,
    YouTubeUploadList,
    YouTubeCategoriesList,
    YouTubeCategory,
)
from ..services.youtube_auth_service import get_active_credential, get_valid_google_credentials
from ..services.youtube_upload_service import (
    YouTubeUploadService,
    YOUTUBE_CATEGORIES,
)
from ..services.video_service import VideoService
from ..services.queue_service import is_redis_available, get_redis_connection
from ..services.job_service import JobService
from ..models.processing_job import ProcessingJob
from ..models.youtube_upload import YouTubeUpload
from ..config import settings
from ..worker.tasks import process_youtube_upload
from rq import Queue
from pathlib import Path

router = APIRouter(prefix="/api/youtube", tags=["youtube"])
logger = logging.getLogger(__name__)


@router.get("/categories", response_model=YouTubeCategoriesList)
def list_categories():
    """Return available YouTube video categories."""
    return YouTubeCategoriesList(
        categories=[
            YouTubeCategory(id=cat_id, name=name)
            for cat_id, name in YOUTUBE_CATEGORIES.items()
        ]
    )


@router.get("/timezone-config", response_model=TimezoneConfig)
def get_timezone_config():
    """Return the configured default timezone for the schedule UI."""
    return TimezoneConfig(default_timezone=settings.DEFAULT_TIMEZONE)


# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------

def _parse_and_validate_schedule(
    scheduled_at_str: str,
    scheduled_timezone: str,
) -> tuple[datetime, str]:
    """
    Parse the user's scheduled_at string + timezone into:
      - a timezone-aware datetime
      - a publish_at ISO-8601 UTC string for YouTube API

    Raises HTTPException if:
      - timezone is invalid
      - datetime cannot be parsed
      - scheduled time is in the past
    """
    # Validate timezone
    try:
        tz = ZoneInfo(scheduled_timezone)
    except (ZoneInfoNotFoundError, KeyError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid timezone: '{scheduled_timezone}'. "
                   "Use an IANA timezone name, e.g. 'Asia/Kolkata' or 'America/New_York'.",
        )

    # Parse datetime
    try:
        # Accept ISO 8601 with or without seconds
        dt_naive = datetime.fromisoformat(scheduled_at_str.replace("Z", ""))
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot parse scheduled_at: '{scheduled_at_str}'. "
                   "Use ISO 8601 format, e.g. '2026-09-20T19:30:00'.",
        )

    # Attach timezone
    dt_local = dt_naive.replace(tzinfo=tz)

    # Convert to UTC
    dt_utc = dt_local.astimezone(timezone.utc)
    now_utc = datetime.now(timezone.utc)

    # Validate future
    if dt_utc <= now_utc:
        raise HTTPException(
            status_code=422,
            detail="Scheduled time must be in the future. "
                   f"Received '{scheduled_at_str}' ({scheduled_timezone}) which is in the past.",
        )

    # Minimum 15 minutes in the future (YouTube's requirement for scheduled uploads)
    min_future = (dt_utc - now_utc).total_seconds()
    if min_future < 900:
        raise HTTPException(
            status_code=422,
            detail="Scheduled time must be at least 15 minutes in the future.",
        )

    # YouTube wants RFC 3339 format: 2026-09-20T14:00:00Z
    publish_at = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt_local, publish_at


# ---------------------------------------------------------------------------
# Create upload or scheduled upload
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=YouTubeUploadResponse,
    status_code=202,
)
def create_youtube_upload(
    body: YouTubeUploadRequest,
    db: Session = Depends(get_db),
):
    """
    Validate the upload request, create an upload record and job, enqueue it.

    Supports:
      upload_mode='upload_now'  — immediate upload
      upload_mode='scheduled'   — upload now with YouTube scheduled publishing
    """
    # 1. Validate YouTube connection
    cred = get_active_credential(db)
    if not cred:
        raise HTTPException(
            status_code=403,
            detail="No YouTube account connected. Please connect your YouTube account first.",
        )

    # 2. Validate video asset
    asset = VideoService.get_asset(db, body.video_asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found.")

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Video file not found on disk. It may have been deleted.",
        )

    # 3. Idempotency check
    existing_yt_id = YouTubeUploadService.check_already_uploaded(db, body.video_asset_id)
    if existing_yt_id:
        raise HTTPException(
            status_code=409,
            detail=f"This video was already successfully uploaded to YouTube "
                   f"(video ID: {existing_yt_id}). Use a different video asset to upload again.",
        )

    # 4. Validate title
    if not body.title or not body.title.strip():
        raise HTTPException(status_code=422, detail="Title is required.")

    # 5. Validate privacy
    if body.privacy not in ("public", "unlisted", "private"):
        raise HTTPException(
            status_code=422,
            detail="Privacy must be 'public', 'unlisted', or 'private'.",
        )

    # 6. Scheduling validation
    scheduled_at_dt: Optional[datetime] = None
    publish_at_str: Optional[str] = None

    if body.upload_mode == "scheduled":
        if not body.scheduled_at:
            raise HTTPException(status_code=422, detail="scheduled_at is required for scheduled uploads.")
        if not body.scheduled_timezone:
            raise HTTPException(status_code=422, detail="scheduled_timezone is required for scheduled uploads.")

        scheduled_at_dt, publish_at_str = _parse_and_validate_schedule(
            body.scheduled_at, body.scheduled_timezone
        )

    # 7. Check Redis
    if not is_redis_available():
        raise HTTPException(
            status_code=503,
            detail="Job queue (Redis) is unavailable. Start Redis and try again.",
        )

    # 8. Create ProcessingJob record
    job = ProcessingJob(
        video_asset_id=body.video_asset_id,
        job_type="youtube_upload",
        status="queued",
    )
    db.add(job)
    db.flush()

    # 9. Create upload record (with scheduling info if applicable)
    upload = YouTubeUploadService.create_upload_record(
        db=db,
        video_asset_id=body.video_asset_id,
        title=body.title.strip(),
        description=body.description,
        tags=body.tags or [],
        privacy=body.privacy,
        category_id=body.category_id,
        job_id=job.id,
        upload_mode=body.upload_mode,
        scheduled_at=scheduled_at_dt,
        scheduled_timezone=body.scheduled_timezone,
        publish_at=publish_at_str,
    )

    db.commit()
    db.refresh(job)

    # 10. Enqueue worker task
    try:
        conn = get_redis_connection()
        q = Queue("video_processing", connection=conn)
        q.enqueue(
            process_youtube_upload,
            upload.id,
            job_timeout=3600,
            result_ttl=86400,
            failure_ttl=86400,
        )
    except Exception as e:
        JobService.mark_failed(db, job, error=f"Failed to enqueue upload: {e}")
        upload.status = "failed"
        upload.error_message = f"Failed to enqueue: {e}"
        db.commit()
        raise HTTPException(status_code=503, detail=f"Failed to queue upload: {e}")

    return YouTubeUploadResponse.model_validate(upload)


# ---------------------------------------------------------------------------
# Get upload status
# ---------------------------------------------------------------------------

@router.get("/uploads/{upload_id}", response_model=YouTubeUploadResponse)
def get_upload_status(upload_id: str, db: Session = Depends(get_db)):
    """Get the status and result of a YouTube upload."""
    upload = YouTubeUploadService.get_upload(db, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload record not found.")
    return YouTubeUploadResponse.model_validate(upload)


# ---------------------------------------------------------------------------
# List uploads
# ---------------------------------------------------------------------------

@router.get("/uploads", response_model=YouTubeUploadList)
def list_uploads(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all YouTube upload records ordered by most recent first."""
    total = db.query(YouTubeUpload).count()
    items = (
        db.query(YouTubeUpload)
        .order_by(YouTubeUpload.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return YouTubeUploadList(
        items=[YouTubeUploadResponse.model_validate(u) for u in items],
        total=total,
    )


# ---------------------------------------------------------------------------
# Reschedule
# ---------------------------------------------------------------------------

@router.post("/uploads/{upload_id}/reschedule", response_model=YouTubeUploadResponse)
def reschedule_upload(
    upload_id: str,
    body: RescheduleRequest,
    db: Session = Depends(get_db),
):
    """
    Change the scheduled publish time of an already-uploaded video.
    The video remains private until the new time.
    """
    upload = YouTubeUploadService.get_upload(db, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    if upload.upload_mode != "scheduled" or not upload.youtube_video_id:
        raise HTTPException(
            status_code=422,
            detail="Only scheduled uploads with a confirmed YouTube video ID can be rescheduled.",
        )

    scheduled_at_dt, publish_at_str = _parse_and_validate_schedule(
        body.scheduled_at, body.scheduled_timezone
    )

    cred = get_active_credential(db)
    if not cred:
        raise HTTPException(status_code=403, detail="No YouTube account connected.")

    try:
        google_creds = get_valid_google_credentials(db)
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        updated = YouTubeUploadService.reschedule_upload(
            db=db,
            upload=upload,
            publish_at_utc=publish_at_str,
            scheduled_at=scheduled_at_dt,
            scheduled_timezone=body.scheduled_timezone,
            google_creds=google_creds,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return YouTubeUploadResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# Cancel schedule
# ---------------------------------------------------------------------------

@router.post("/uploads/{upload_id}/cancel-schedule", response_model=YouTubeUploadResponse)
def cancel_schedule(
    upload_id: str,
    db: Session = Depends(get_db),
):
    """
    Cancel the scheduled publish of a video.
    The video remains on YouTube as private (not deleted).
    """
    upload = YouTubeUploadService.get_upload(db, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")

    if not upload.youtube_video_id:
        raise HTTPException(
            status_code=422,
            detail="This upload has not been confirmed on YouTube yet.",
        )

    if upload.status not in ("scheduled",):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot cancel schedule: upload is in status '{upload.status}'. "
                   "Only 'scheduled' uploads can have their schedule cancelled.",
        )

    cred = get_active_credential(db)
    if not cred:
        raise HTTPException(status_code=403, detail="No YouTube account connected.")

    try:
        google_creds = get_valid_google_credentials(db)
    except RuntimeError as e:
        raise HTTPException(status_code=403, detail=str(e))

    try:
        updated = YouTubeUploadService.cancel_schedule(
            db=db,
            upload=upload,
            google_creds=google_creds,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return YouTubeUploadResponse.model_validate(updated)
