"""Video service: upload handling, VideoAsset CRUD.
Probe logic lives in ffmpeg_service; this module handles storage + DB.
"""
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.video_asset import VideoAsset
from ..schemas.video import VideoAssetCreate  # noqa: F401  kept for import compat


ALLOWED_EXTENSIONS = {".mp4", ".mov"}
ALLOWED_MIME_TYPES = {"video/mp4", "video/quicktime"}


class VideoService:

    async def save_uploaded_file(
        self,
        file_bytes: bytes,
        original_filename: str,
        source_media_id: Optional[str] = None,
        caption: Optional[str] = None,
        permalink: Optional[str] = None,
        instagram_timestamp: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> VideoAsset:
        """
        Validate extension, write to uploads dir, probe with ffprobe,
        create and persist a VideoAsset.
        """
        from ..services.ffmpeg_service import probe_video

        ext = Path(original_filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        asset_id = str(uuid.uuid4())
        dest_filename = f"{asset_id}{ext}"
        dest_path = settings.uploads_dir / dest_filename
        settings.ensure_dirs()

        dest_path.write_bytes(file_bytes)

        probe = await probe_video(dest_path)
        mime_type = mimetypes.guess_type(original_filename)[0] or "video/mp4"

        asset = VideoAsset(
            id=asset_id,
            source="manual",
            source_media_id=source_media_id,
            file_path=str(dest_path),
            original_filename=original_filename,
            mime_type=mime_type,
            file_size=os.path.getsize(dest_path),
            width=probe.get("width"),
            height=probe.get("height"),
            duration_seconds=probe.get("duration_seconds"),
            aspect_ratio=probe.get("aspect_ratio", "unknown"),
            codec_name=probe.get("codec_name"),
            fps=probe.get("fps"),
            has_audio=str(probe.get("has_audio", False)).lower(),
            caption=caption,
            permalink=permalink,
            instagram_timestamp=instagram_timestamp,
            thumbnail_url=thumbnail_url,
        )

        if db:
            db.add(asset)
            db.commit()
            db.refresh(asset)

        return asset

    # ------------------------------------------------------------------
    # Aspect ratio (kept for backward compat)
    # ------------------------------------------------------------------

    @staticmethod
    def classify_aspect_ratio(width: Optional[int], height: Optional[int]) -> str:
        from ..services.ffmpeg_service import classify_aspect_ratio
        return classify_aspect_ratio(width, height)

    # ------------------------------------------------------------------
    # DB queries
    # ------------------------------------------------------------------

    @staticmethod
    def list_assets(db: Session, skip: int = 0, limit: int = 50) -> tuple[list[VideoAsset], int]:
        total = db.query(VideoAsset).count()
        items = db.query(VideoAsset).offset(skip).limit(limit).all()
        return items, total

    @staticmethod
    def get_asset(db: Session, asset_id: str) -> Optional[VideoAsset]:
        return db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()

    @staticmethod
    def delete_asset(db: Session, asset_id: str) -> bool:
        asset = db.query(VideoAsset).filter(VideoAsset.id == asset_id).first()
        if not asset:
            return False
        try:
            Path(asset.file_path).unlink(missing_ok=True)
        except Exception:
            pass
        db.delete(asset)
        db.commit()
        return True


video_service = VideoService()
