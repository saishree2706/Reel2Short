"""
Storage lifecycle / cleanup service.

Handles:
- Deleting video files after confirmed upload
- Retaining files for failed uploads up to TEMP_VIDEO_RETENTION_HOURS
- Cleaning up expired temporary files
"""
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.video_asset import VideoAsset
from ..models.youtube_upload import YouTubeUpload

logger = logging.getLogger(__name__)


class CleanupService:

    @staticmethod
    def delete_video_files(asset: VideoAsset) -> bool:
        """
        Delete the physical file for a VideoAsset.
        Returns True if file was deleted, False if it didn't exist.
        DOES NOT delete the database record.
        """
        if not asset.file_path:
            return False
        path = Path(asset.file_path)
        if path.exists():
            try:
                path.unlink()
                logger.info("Deleted video file: %s", path.name)
                return True
            except OSError as e:
                logger.error("Failed to delete %s: %s", path.name, e)
                return False
        return False

    @staticmethod
    def cleanup_after_successful_upload(
        db: Session,
        upload: YouTubeUpload,
    ) -> int:
        """
        After confirmed YouTube upload success:
        1. Delete the uploaded video asset's file.
        2. If it was a converted asset, also delete the original's file.
        Returns number of files deleted.
        """
        if upload.upload_confirmed != "true" or not upload.youtube_video_id:
            logger.warning("cleanup_after_successful_upload called on unconfirmed upload")
            return 0

        deleted = 0
        asset = db.query(VideoAsset).filter(
            VideoAsset.id == upload.video_asset_id
        ).first()

        if not asset:
            return 0

        # Delete the uploaded file (may be original or converted)
        if CleanupService.delete_video_files(asset):
            deleted += 1

        # If this was a converted asset, also delete the original if it still exists
        if asset.parent_asset_id:
            original = db.query(VideoAsset).filter(
                VideoAsset.id == asset.parent_asset_id
            ).first()
            if original:
                if CleanupService.delete_video_files(original):
                    deleted += 1

        logger.info(
            "Cleanup after upload %s: deleted %d files", upload.id, deleted
        )
        return deleted

    @staticmethod
    def cleanup_expired_temp_files(db: Session) -> int:
        """
        Find and delete temporary video files for:
        - Failed uploads older than TEMP_VIDEO_RETENTION_HOURS
        - Orphaned assets with no associated upload
        Returns number of files deleted.
        """
        retention_hours = settings.TEMP_VIDEO_RETENTION_HOURS
        cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)

        deleted = 0

        # Find failed uploads past retention
        expired_uploads = (
            db.query(YouTubeUpload)
            .filter(
                YouTubeUpload.status == "failed",
                YouTubeUpload.updated_at < cutoff,
            )
            .all()
        )

        safe_statuses = {"queued", "authorizing", "uploading", "processing"}

        for upload in expired_uploads:
            asset = db.query(VideoAsset).filter(
                VideoAsset.id == upload.video_asset_id
            ).first()
            if asset:
                # Double-check: no active upload using this asset
                active = (
                    db.query(YouTubeUpload)
                    .filter(
                        YouTubeUpload.video_asset_id == asset.id,
                        YouTubeUpload.status.in_(safe_statuses),
                    )
                    .first()
                )
                if not active:
                    if CleanupService.delete_video_files(asset):
                        deleted += 1

        if deleted:
            logger.info("Expired temp cleanup: deleted %d files", deleted)
        return deleted

    @staticmethod
    def cleanup_incomplete_ffmpeg_outputs(db: Session) -> int:
        """
        Delete any converted files in storage/converted/ that have no
        corresponding VideoAsset record (abandoned FFmpeg runs).
        """
        converted_dir = settings.converted_dir
        if not converted_dir.exists():
            return 0

        deleted = 0
        for f in converted_dir.iterdir():
            if not f.is_file():
                continue
            # Check if there's a VideoAsset pointing to this file
            asset = (
                db.query(VideoAsset)
                .filter(VideoAsset.file_path == str(f))
                .first()
            )
            if not asset:
                try:
                    f.unlink()
                    deleted += 1
                    logger.info("Deleted orphaned converted file: %s", f.name)
                except OSError:
                    pass

        return deleted


cleanup_service = CleanupService()

