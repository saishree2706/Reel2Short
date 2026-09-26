"""Jobs API — job status and listing."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.job import JobResponse
from ..schemas.video import VideoAssetResponse
from ..services.job_service import JobService
from ..services.video_service import VideoService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get processing job status.
    When completed, output_asset_id points to the converted VideoAsset.
    """
    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobResponse.model_validate(job)


@router.get("/{job_id}/result", response_model=VideoAssetResponse)
def get_job_result(job_id: str, db: Session = Depends(get_db)):
    """Return the output VideoAsset when the job is completed."""
    job = JobService.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed" or not job.output_asset_id:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not completed yet (status: {job.status}).",
        )
    asset = VideoService.get_asset(db, job.output_asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Output video asset not found.")
    return VideoAssetResponse.model_validate(asset)

