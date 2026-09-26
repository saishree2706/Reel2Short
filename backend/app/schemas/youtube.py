"""Pydantic schemas for YouTube auth, upload, scheduling, and AI metadata."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# Auth / connection status
# ---------------------------------------------------------------------------

class YouTubeConnectionStatus(BaseModel):
    connected: bool
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    # NOTE: access_token and refresh_token are NEVER included here
    state: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Upload request / response
# ---------------------------------------------------------------------------

class YouTubeUploadRequest(BaseModel):
    video_asset_id: str
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=5000)
    tags: Optional[List[str]] = Field(default_factory=list)
    privacy: str = Field("private", pattern="^(public|unlisted|private)$")
    category_id: Optional[str] = None

    # Stage 4: scheduling
    upload_mode: str = Field("upload_now", pattern="^(upload_now|scheduled)$")
    scheduled_at: Optional[str] = None   # ISO 8601 datetime string from the browser
    scheduled_timezone: Optional[str] = None  # IANA timezone name


class YouTubeUploadResponse(BaseModel):
    id: str
    video_asset_id: str
    job_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    tags: Optional[str] = None        # stored as JSON string
    privacy: str
    category_id: Optional[str] = None
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    status: str
    bytes_uploaded: Optional[int] = None
    total_bytes: Optional[int] = None
    error_message: Optional[str] = None
    upload_confirmed: str = "false"
    # Scheduling fields
    upload_mode: str = "upload_now"
    scheduled_at: Optional[datetime] = None
    scheduled_timezone: Optional[str] = None
    publish_at: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class YouTubeUploadList(BaseModel):
    items: List[YouTubeUploadResponse]
    total: int


# ---------------------------------------------------------------------------
# Scheduling actions
# ---------------------------------------------------------------------------

class RescheduleRequest(BaseModel):
    scheduled_at: str = Field(..., description="ISO 8601 datetime in the specified timezone")
    scheduled_timezone: str = Field(..., min_length=1, max_length=64)


# ---------------------------------------------------------------------------
# YouTube categories helper
# ---------------------------------------------------------------------------

class YouTubeCategory(BaseModel):
    id: str
    name: str


class YouTubeCategoriesList(BaseModel):
    categories: List[YouTubeCategory]


# ---------------------------------------------------------------------------
# AI metadata schemas
# ---------------------------------------------------------------------------

class AIMetadataRequestSchema(BaseModel):
    """Schema for the generate-metadata API request body."""
    description: str = Field(..., min_length=1, max_length=2000)
    keywords: Optional[List[str]] = Field(default_factory=list)
    content_type: Optional[str] = Field(None, max_length=100)
    target_audience: Optional[str] = Field(None, max_length=200)
    language: Optional[str] = Field("English", max_length=50)
    tone: Optional[str] = Field(None, max_length=100)


class ThumbnailConceptSchema(BaseModel):
    concept: str
    text: str
    visual_moment: str


class AIMetadataResponseSchema(BaseModel):
    titles: List[str]
    description: str
    hashtags: List[str]
    tags: List[str]
    category: str
    hook: str
    thumbnail: ThumbnailConceptSchema


# ---------------------------------------------------------------------------
# Timezone config for the frontend
# ---------------------------------------------------------------------------

class TimezoneConfig(BaseModel):
    default_timezone: str
