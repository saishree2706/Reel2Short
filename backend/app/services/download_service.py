"""Download service — streams Instagram Reels to disk."""
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models.video_asset import VideoAsset

_CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=5.0)


class DownloadService:

    @staticmethod
    async def download_reel(
        media_url: str,
        media_id: str,
        caption: Optional[str] = None,
        permalink: Optional[str] = None,
        instagram_timestamp: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> VideoAsset:
        """
        Stream a video from media_url to a temp file, then move it to
        storage/downloads/.  Probes with ffprobe and persists a VideoAsset.
        """
        from ..services.ffmpeg_service import probe_video

        settings.ensure_dirs()

        tmp_id = str(uuid.uuid4())
        tmp_path = settings.temp_dir / f"{tmp_id}.mp4"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                async with client.stream("GET", media_url) as response:
                    response.raise_for_status()
                    with tmp_path.open("wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=_CHUNK_SIZE):
                            f.write(chunk)
        except httpx.HTTPStatusError as e:
            _cleanup(tmp_path)
            raise RuntimeError(
                f"Download failed with HTTP {e.response.status_code}: {e.response.text[:200]}"
            )
        except httpx.RequestError as e:
            _cleanup(tmp_path)
            raise RuntimeError(f"Network error during download: {e}")

        size = tmp_path.stat().st_size
        if size == 0:
            _cleanup(tmp_path)
            raise RuntimeError("Downloaded file is empty.")

        asset_id = str(uuid.uuid4())
        dest_filename = f"{asset_id}.mp4"
        dest_path = settings.downloads_dir / dest_filename
        shutil.move(str(tmp_path), str(dest_path))

        probe = await probe_video(dest_path)

        asset = VideoAsset(
            id=asset_id,
            source="instagram",
            source_media_id=media_id,
            source_url=media_url,
            file_path=str(dest_path),
            original_filename=dest_filename,
            mime_type="video/mp4",
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


def _cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


download_service = DownloadService()
