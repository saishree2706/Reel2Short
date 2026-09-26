"""Pydantic schemas for Instagram media."""
from pydantic import BaseModel
from typing import Optional


class InstagramMedia(BaseModel):
    """Normalized Instagram media item."""
    id: str
    media_type: str
    media_product_type: Optional[str] = None
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    permalink: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[str] = None

    @property
    def is_reel(self) -> bool:
        return (
            self.media_type == "VIDEO"
            and self.media_product_type == "REELS"
        )

    @property
    def download_available(self) -> bool:
        return self.media_url is not None


class InstagramMediaList(BaseModel):
    items: list[InstagramMedia]
    next_cursor: Optional[str] = None
    has_more: bool = False


class ReelStatusResponse(BaseModel):
    media_id: str
    download_available: bool
    manual_upload_required: bool
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[str] = None
    permalink: Optional[str] = None

