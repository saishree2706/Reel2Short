"""Pydantic schemas for ProcessingJob."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobCreate(BaseModel):
    video_asset_id: str
    job_type: str = "convert"
    conversion_mode: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    video_asset_id: str
    job_type: str
    conversion_mode: Optional[str] = None
    status: str
    progress: Optional[float] = None
    error_message: Optional[str] = None
    output_asset_id: Optional[str] = None
    retry_count: str = "0"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ConvertRequest(BaseModel):
    mode: str  # "crop" | "blur_background"

