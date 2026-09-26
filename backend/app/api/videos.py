"""Videos API endpoints: download, upload, list, detail, probe, convert, preview, delete, AI metadata."""
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.job import ConvertRequest, JobResponse
from ..schemas.video import ProbeResponse, VideoAssetList, VideoAssetResponse
from ..schemas.youtube import AIMetadataRequestSchema
from ..services.download_service import DownloadService
from ..services.ffmpeg_service import probe_video
from ..services.job_service import JobService, VALID_MODES
from ..services.queue_service import enqueue_job, is_redis_available
from ..services.video_service import ALLOWED_EXTENSIONS, VideoService

router = APIRouter(prefix="/api/videos", tags=["videos"])

_VALID_MODES = VALID_MODES


# ------------------------------------------------------------------
# Download from Instagram
# ------------------------------------------------------------------


@router.post("/download", response_model=VideoAssetResponse, status_code=201)
async def download_reel(
    media_id: str = Form(...),
    media_url: str = Form(...),
    caption: Optional[str] = Form(None),
    permalink: Optional[str] = Form(None),
    instagram_timestamp: Optional[str] = Form(None),
    thumbnail_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Stream-download a Reel from Instagram's media_url and save it locally.
    """
    try:
        asset = await DownloadService.download_reel(
            media_url=media_url,
            media_id=media_id,
            caption=caption,
            permalink=permalink,
            instagram_timestamp=instagram_timestamp,
            thumbnail_url=thumbnail_url,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")
    return VideoAssetResponse.model_validate(asset)


# ------------------------------------------------------------------
# Manual upload
# ------------------------------------------------------------------


@router.post("/upload", response_model=VideoAssetResponse, status_code=201)
async def upload_video(
    file: UploadFile = File(..., description="MP4 or MOV video file"),
    source_media_id: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    permalink: Optional[str] = Form(None),
    instagram_timestamp: Optional[str] = Form(None),
    thumbnail_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Accept a manually uploaded video (MP4 or MOV)."""
    filename = file.filename or "upload.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Allowed: .mp4, .mov",
        )
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    try:
        asset = await VideoService().save_uploaded_file(
            file_bytes=contents,
            original_filename=filename,
            source_media_id=source_media_id,
            caption=caption,
            permalink=permalink,
            instagram_timestamp=instagram_timestamp,
            thumbnail_url=thumbnail_url,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return VideoAssetResponse.model_validate(asset)


# ------------------------------------------------------------------
# List videos
# ------------------------------------------------------------------


@router.get("", response_model=VideoAssetList)
def list_videos(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Return all stored VideoAssets with pagination."""
    items, total = VideoService.list_assets(db, skip=skip, limit=limit)
    return VideoAssetList(
        items=[VideoAssetResponse.model_validate(a) for a in items],
        total=total,
    )


# ------------------------------------------------------------------
# Single video detail  (must come before /{asset_id}/{sub} routes)
# ------------------------------------------------------------------


@router.get("/{asset_id}", response_model=VideoAssetResponse)
def get_video(asset_id: str, db: Session = Depends(get_db)):
    """Return metadata for a single VideoAsset."""
    asset = VideoService.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found.")
    return VideoAssetResponse.model_validate(asset)


# ------------------------------------------------------------------
# Probe (ffprobe metadata)
# ------------------------------------------------------------------


@router.get("/{asset_id}/probe", response_model=ProbeResponse)
async def probe_video_endpoint(asset_id: str, db: Session = Depends(get_db)):
    """
    Run ffprobe on the stored video and return detailed metadata.
    Also updates the VideoAsset record with fresh metadata.
    """
    asset = VideoService.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found.")

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk.")

    result = await probe_video(file_path)

    # Persist fresh metadata back to the asset
    asset.width = result.get("width")
    asset.height = result.get("height")
    asset.duration_seconds = result.get("duration_seconds")
    asset.aspect_ratio = result.get("aspect_ratio", "unknown")
    asset.codec_name = result.get("codec_name")
    asset.fps = result.get("fps")
    has_audio = result.get("has_audio")
    asset.has_audio = str(has_audio).lower() if has_audio is not None else None
    db.commit()

    has_audio_val = result.get("has_audio")
    return ProbeResponse(
        asset_id=asset_id,
        width=result.get("width"),
        height=result.get("height"),
        duration_seconds=result.get("duration_seconds"),
        codec_name=result.get("codec_name"),
        fps=result.get("fps"),
        has_audio=bool(has_audio_val) if has_audio_val is not None else None,
        format_name=result.get("format_name"),
        aspect_ratio=result.get("aspect_ratio", "unknown"),
        file_size=result.get("file_size"),
    )


# ------------------------------------------------------------------
# Convert (async job creation)
# ------------------------------------------------------------------


@router.post("/{asset_id}/convert", response_model=JobResponse, status_code=202)
def convert_video(
    asset_id: str,
    body: ConvertRequest,
    db: Session = Depends(get_db),
):
    """
    Create a conversion job for horizontal → vertical conversion.
    Returns immediately with the queued job. FFmpeg runs in the worker.
    """
    # Validate mode
    if body.mode not in _VALID_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid conversion mode '{body.mode}'. Allowed: {sorted(_VALID_MODES)}",
        )

    # Validate asset
    asset = VideoService.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found.")

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk.")

    # Check Redis
    if not is_redis_available():
        raise HTTPException(
            status_code=503,
            detail="Job queue (Redis) is unavailable. Start Redis and try again.",
        )

    # Create job record
    job = JobService.create_job(
        db=db,
        video_asset_id=asset_id,
        conversion_mode=body.mode,
    )

    # Enqueue
    try:
        enqueue_job(job.id)
    except Exception as e:
        JobService.mark_failed(db, job, error=f"Failed to enqueue: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to queue job: {e}")

    return JobResponse.model_validate(job)


# ------------------------------------------------------------------
# Preview / serve (with range request support)
# ------------------------------------------------------------------


@router.get("/{asset_id}/preview")
@router.get("/{asset_id}/file")
async def serve_video(asset_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Stream video with Range request support for browser playback.
    Works for both original and converted assets.
    Does not expose internal filesystem paths.
    """
    asset = VideoService.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found.")

    file_path = Path(asset.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk.")

    file_size = file_path.stat().st_size
    mime_type = asset.mime_type or "video/mp4"
    range_header = request.headers.get("Range")

    if range_header:
        # Parse Range: bytes=start-end
        try:
            range_val = range_header.strip().replace("bytes=", "")
            start_str, _, end_str = range_val.partition("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            end = min(end, file_size - 1)
            chunk_size = end - start + 1
        except ValueError:
            raise HTTPException(status_code=416, detail="Invalid Range header.")

        def iter_range():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=mime_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    # Full file streaming
    def iter_file():
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Disposition": f'inline; filename="{asset.original_filename}"',
        },
    )


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------


@router.delete("/{asset_id}", status_code=204)
def delete_video(asset_id: str, db: Session = Depends(get_db)):
    """Delete a VideoAsset and its file from disk."""
    deleted = VideoService.delete_asset(db, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Video not found.")


# ------------------------------------------------------------------
# AI Metadata Generation (Stage 4)
# ------------------------------------------------------------------


@router.post("/{asset_id}/generate-metadata")
def generate_metadata_endpoint(
    asset_id: str,
    body: AIMetadataRequestSchema,
    db: Session = Depends(get_db),
):
    """
    Generate YouTube Shorts metadata using Gemini AI.

    Gathers available video context (caption, duration, aspect ratio)
    and calls Gemini with the user-provided description.

    Returns structured metadata suggestions for the user to review/edit.
    This endpoint NEVER auto-uploads anything.
    """
    from ..services.ai_service import AIMetadataRequest, generate_metadata as ai_generate

    # 1. Validate video exists
    asset = VideoService.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found.")

    # 2. Build AI request with video context
    ai_request = AIMetadataRequest(
        description=body.description,
        keywords=body.keywords or [],
        content_type=body.content_type,
        target_audience=body.target_audience,
        language=body.language or "English",
        tone=body.tone,
        # Auto-populated from asset
        instagram_caption=asset.caption,
        duration_seconds=asset.duration_seconds,
        aspect_ratio=asset.aspect_ratio,
        is_converted=(asset.source == "converted"),
    )

    # 3. Call AI
    try:
        result = ai_generate(ai_request)
    except RuntimeError as e:
        err_msg = str(e)
        if "AI_API_KEY is not configured" in err_msg:
            raise HTTPException(status_code=503, detail=err_msg)
        if "quota" in err_msg.lower():
            raise HTTPException(
                status_code=429,
                detail="AI quota exceeded. Please try again later.",
            )
        raise HTTPException(status_code=502, detail=err_msg)

    # 4. Return structured response — no API keys, no internals
    return {
        "titles": result.titles,
        "description": result.description,
        "hashtags": result.hashtags,
        "tags": result.tags,
        "category": result.category,
        "hook": result.hook,
        "thumbnail": {
            "concept": result.thumbnail.concept,
            "text": result.thumbnail.text,
            "visual_moment": result.thumbnail.visual_moment,
        },
    }
