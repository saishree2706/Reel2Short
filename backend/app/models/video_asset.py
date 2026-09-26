"""VideoAsset SQLAlchemy model — the common internal object for every video."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String
from ..database import Base


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Where this video came from: "instagram" | "manual"
    source = Column(String, nullable=False)

    # Instagram media id (only when source == "instagram")
    source_media_id = Column(String, nullable=True)

    # Original download / media_url
    source_url = Column(String, nullable=True)

    # Absolute or relative path to the file on disk
    file_path = Column(String, nullable=False)

    # Original filename (e.g. "reel_abc123.mp4")
    original_filename = Column(String, nullable=False)

    # MIME type: "video/mp4" | "video/quicktime"
    mime_type = Column(String, nullable=True)

    # File size in bytes
    file_size = Column(Integer, nullable=True)

    # ffprobe-detected dimensions
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    # ffprobe-detected duration in seconds
    duration_seconds = Column(Float, nullable=True)

    # "vertical" | "square" | "horizontal" | "unknown"
    aspect_ratio = Column(String, nullable=True)

    # Additional ffprobe fields
    codec_name = Column(String, nullable=True)
    fps = Column(Float, nullable=True)
    has_audio = Column(String, nullable=True)  # "true"/"false"/None stored as string for SQLite compat

    # Instagram caption / description
    caption = Column(String, nullable=True)

    # Instagram permalink
    permalink = Column(String, nullable=True)

    # Instagram post date
    instagram_timestamp = Column(String, nullable=True)

    # Thumbnail URL from Instagram
    thumbnail_url = Column(String, nullable=True)

    # If this is a converted asset, point to the original
    parent_asset_id = Column(String, nullable=True, index=True)

    # Conversion mode used to create this asset: "crop" | "blur_background" | None
    conversion_mode = Column(String, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


