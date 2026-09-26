"""
Worker tasks: video conversion, YouTube upload, and cleanup.

All functions here are called by rq workers.
They run synchronously — the worker process is the right place for blocking I/O.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


# ===========================================================================
# Task 1: Video conversion (Stage 2 — unchanged)
# ===========================================================================

def process_job(job_id: str) -> dict:
    """
    Convert a video using FFmpeg.

    Entry point called by rq for each conversion job.
    """
    from ..database import SessionLocal
    from ..models.processing_job import ProcessingJob
    from ..models.video_asset import VideoAsset
    from ..services.job_service import JobService
    from ..services.ffmpeg_service import (
        get_ffmpeg,
        build_crop_cmd,
        build_blur_cmd,
        run_ffmpeg_sync,
        probe_video_sync,
    )
    from ..config import settings

    db = SessionLocal()
    output_path: Path | None = None

    try:
        # --- 1. Load job ---
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error("Job %s not found in DB", job_id)
            return {"error": "Job not found"}

        # --- 2. Mark processing ---
        JobService.mark_processing(db, job)
        logger.info("Worker: processing job %s (%s)", job_id, job.conversion_mode)

        # --- 3. Load source asset ---
        source = db.query(VideoAsset).filter(VideoAsset.id == job.video_asset_id).first()
        if not source:
            raise RuntimeError(f"Source video asset {job.video_asset_id} not found")

        src_path = Path(source.file_path)
        if not src_path.exists():
            raise RuntimeError(f"Source file not found on disk: {src_path.name}")

        # --- 4. Build FFmpeg command ---
        mode = job.conversion_mode
        if mode not in ("crop", "blur_background"):
            raise RuntimeError(f"Unknown conversion mode: {mode}")

        settings.ensure_dirs()
        output_id = str(uuid.uuid4())
        output_filename = f"{output_id}_converted.mp4"
        output_path = settings.converted_dir / output_filename

        ffmpeg = get_ffmpeg()
        if mode == "crop":
            cmd = build_crop_cmd(src_path, output_path, ffmpeg)
        else:
            cmd = build_blur_cmd(src_path, output_path, ffmpeg)

        logger.info("Worker: running FFmpeg for job %s", job_id)

        # --- 5. Run FFmpeg ---
        returncode, stderr = run_ffmpeg_sync(cmd, timeout=600)

        if returncode != 0:
            raise RuntimeError(
                f"FFmpeg failed (exit {returncode}).\n"
                f"Stderr (last 500 chars): {stderr[-500:]}"
            )

        # --- 6. Validate output ---
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg produced no output file.")

        # --- 7. Probe output and create converted VideoAsset ---
        probe = probe_video_sync(output_path)

        converted_asset = VideoAsset(
            id=output_id,
            source="converted",
            file_path=str(output_path),
            original_filename=output_filename,
            mime_type="video/mp4",
            file_size=os.path.getsize(output_path),
            width=probe.get("width"),
            height=probe.get("height"),
            duration_seconds=probe.get("duration_seconds"),
            aspect_ratio=probe.get("aspect_ratio", "vertical"),
            codec_name=probe.get("codec_name"),
            fps=probe.get("fps"),
            has_audio=str(probe.get("has_audio", False)).lower(),
            caption=source.caption,
            parent_asset_id=source.id,
            conversion_mode=mode,
        )
        db.add(converted_asset)
        db.flush()

        # --- 8. Mark job completed ---
        JobService.mark_completed(db, job, output_asset_id=output_id)
        db.commit()

        logger.info("Worker: job %s completed → asset %s", job_id, output_id)
        return {"status": "completed", "output_asset_id": output_id}

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Worker: job %s failed: %s", job_id, error_msg)

        # Clean up incomplete output file
        if output_path and output_path.exists():
            try:
                output_path.unlink()
                logger.info("Worker: cleaned up incomplete output %s", output_path.name)
            except OSError:
                pass

        # Mark job failed
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if job:
                JobService.mark_failed(db, job, error=error_msg)
        except Exception:
            pass

        raise  # re-raise so rq records the failure

    finally:
        db.close()


# ===========================================================================
# Task 2: YouTube upload (Stage 3)
# ===========================================================================

def process_youtube_upload(upload_id: str) -> dict:
    """
    Upload a video to YouTube using resumable upload.

    Entry point called by rq for youtube_upload jobs.
    """
    from ..database import SessionLocal
    from ..models.youtube_upload import YouTubeUpload
    from ..models.processing_job import ProcessingJob
    from ..services.youtube_auth_service import get_valid_google_credentials
    from ..services.youtube_upload_service import YouTubeUploadService
    from ..services.cleanup_service import CleanupService

    db = SessionLocal()

    try:
        # 1. Load upload record
        upload = db.query(YouTubeUpload).filter(YouTubeUpload.id == upload_id).first()
        if not upload:
            logger.error("Upload record %s not found", upload_id)
            return {"error": "Upload not found"}

        # 2. Idempotency: already uploaded?
        if upload.upload_confirmed == "true" and upload.youtube_video_id:
            logger.info("Upload %s already confirmed — skipping", upload_id)
            return {
                "status": "completed",
                "youtube_video_id": upload.youtube_video_id,
            }

        # 3. Mark as authorizing
        upload.status = "authorizing"
        db.commit()

        # 4. Get (and auto-refresh if needed) valid credentials
        try:
            google_creds = get_valid_google_credentials(db)
        except RuntimeError as e:
            upload.status = "failed"
            upload.error_message = str(e)
            db.commit()
            raise

        # 5. Perform upload
        logger.info("Worker: starting YouTube upload for record %s", upload_id)
        youtube_video_id = YouTubeUploadService.perform_upload(
            db=db,
            upload_record=upload,
            google_creds=google_creds,
        )

        # 6. Update associated ProcessingJob if present
        if upload.job_id:
            job = db.query(ProcessingJob).filter(
                ProcessingJob.id == upload.job_id
            ).first()
            if job:
                job.status = "completed"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()

        # 7. Delete temporary files after confirmed success
        CleanupService.cleanup_after_successful_upload(db, upload)

        logger.info(
            "Worker: YouTube upload %s completed → https://youtube.com/watch?v=%s",
            upload_id,
            youtube_video_id,
        )
        return {"status": "completed", "youtube_video_id": youtube_video_id}

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Worker: YouTube upload %s failed: %s", upload_id, error_msg)

        # Mark upload and job as failed
        try:
            upload = db.query(YouTubeUpload).filter(YouTubeUpload.id == upload_id).first()
            if upload:
                upload.status = "failed"
                upload.error_message = error_msg[:2000]
                db.commit()

            # Also mark the ProcessingJob as failed
            if upload and upload.job_id:
                job = db.query(ProcessingJob).filter(
                    ProcessingJob.id == upload.job_id
                ).first()
                if job:
                    job.status = "failed"
                    job.error_message = error_msg[:1000]
                    db.commit()
        except Exception:
            pass

        raise

    finally:
        db.close()


# ===========================================================================
# Task 3: Storage cleanup (Stage 3)
# ===========================================================================

def run_cleanup() -> dict:
    """
    Periodic storage cleanup task.
    Deletes expired temp files for failed uploads.
    Removes orphaned FFmpeg outputs.
    """
    from ..database import SessionLocal
    from ..services.cleanup_service import CleanupService

    db = SessionLocal()
    try:
        expired_deleted = CleanupService.cleanup_expired_temp_files(db)
        orphan_deleted = CleanupService.cleanup_incomplete_ffmpeg_outputs(db)
        total = expired_deleted + orphan_deleted
        logger.info(
            "Cleanup task: deleted %d expired + %d orphaned = %d files total",
            expired_deleted,
            orphan_deleted,
            total,
        )
        return {
            "status": "completed",
            "expired_deleted": expired_deleted,
            "orphan_deleted": orphan_deleted,
        }
    except Exception as e:
        logger.error("Cleanup task failed: %s", e)
        raise
    finally:
        db.close()
