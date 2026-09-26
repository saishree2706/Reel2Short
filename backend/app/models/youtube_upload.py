"""YouTubeUpload — tracks the lifecycle of each YouTube upload attempt."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text
from ..database import Base


class YouTubeUpload(Base):
    __tablename__ = "youtube_uploads"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # FK → video_assets.id (the video file being uploaded)
    video_asset_id = Column(String, nullable=False, index=True)

    # FK → processing_jobs.id (the upload job)
    job_id = Column(String, nullable=True, index=True)

    # YouTube metadata entered by the user
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)          # JSON list stored as text
    privacy = Column(String, nullable=False, default="private")   # public|unlisted|private
    category_id = Column(String, nullable=True)  # YouTube category ID

    # Results — populated after successful upload
    youtube_video_id = Column(String, nullable=True, index=True)
    youtube_url = Column(String, nullable=True)

    # Upload progress tracking
    # "queued"|"authorizing"|"uploading"|"processing"|"scheduled"|"completed"|"failed"
    status = Column(String, nullable=False, default="queued")
    bytes_uploaded = Column(Integer, nullable=True)
    total_bytes = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Idempotency: prevent double uploads
    # Set to True once YouTube confirms the video ID
    upload_confirmed = Column(String, nullable=False, default="false")

    # Stage 4: scheduling
    # "upload_now" | "scheduled"
    upload_mode = Column(String, nullable=False, default="upload_now")
    # User's requested publish time (in their timezone — stored for display)
    scheduled_at = Column(DateTime, nullable=True)
    # IANA timezone name, e.g. "Asia/Kolkata"
    scheduled_timezone = Column(String, nullable=True)
    # ISO 8601 UTC string sent to YouTube API (publishAt)
    publish_at = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime, nullable=True)
