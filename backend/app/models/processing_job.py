"""ProcessingJob SQLAlchemy model."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Float, String
from ..database import Base


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # FK to video_assets.id (source video)
    video_asset_id = Column(String, nullable=False, index=True)

    # "convert" (or future types)
    job_type = Column(String, nullable=False, default="convert")

    # Conversion parameters: "crop" | "blur_background"
    conversion_mode = Column(String, nullable=True)

    # "queued" | "processing" | "completed" | "failed"
    status = Column(String, nullable=False, default="queued")

    # Optional: float 0.0–1.0 (not faked; only set if reliable)
    progress = Column(Float, nullable=True)

    # Error message if failed
    error_message = Column(String, nullable=True)

    # FK to video_assets.id for the output (set when completed)
    output_asset_id = Column(String, nullable=True)

    # Retry tracking
    retry_count = Column(String, nullable=False, default="0")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

