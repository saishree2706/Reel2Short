"""Pydantic schemas for VideoAsset."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class VideoAssetBase(BaseModel):
    source: str
    source_media_id: Optional[str] = None
    source_url: Optional[str] = None
    file_path: str
    original_filename: str
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    codec_name: Optional[str] = None
    fps: Optional[float] = None
    has_audio: Optional[str] = None
    caption: Optional[str] = None
    permalink: Optional[str] = None
    instagram_timestamp: Optional[str] = None
    thumbnail_url: Optional[str] = None
    parent_asset_id: Optional[str] = None
    conversion_mode: Optional[str] = None


class VideoAssetCreate(VideoAssetBase):
    pass


class VideoAssetResponse(VideoAssetBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VideoAssetList(BaseModel):
    items: list[VideoAssetResponse]
    total: int


class ProbeResponse(BaseModel):
    """Result of running ffprobe on a video asset."""
    asset_id: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    codec_name: Optional[str] = None
    fps: Optional[float] = None
    has_audio: Optional[bool] = None
    format_name: Optional[str] = None
    aspect_ratio: str
    file_size: Optional[int] = None
