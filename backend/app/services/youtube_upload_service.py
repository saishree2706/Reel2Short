"""
YouTube upload service.

Handles resumable uploads to YouTube Data API v3.
Streams the video file — does NOT load it into memory.
Supports both immediate upload and scheduled publishing via publishAt.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..models.youtube_upload import YouTubeUpload
from ..models.video_asset import VideoAsset

logger = logging.getLogger(__name__)

# YouTube video category IDs (common ones)
YOUTUBE_CATEGORIES = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}

CHUNK_SIZE = 1024 * 1024 * 5  # 5 MB per chunk for resumable upload


class YouTubeUploadService:

    @staticmethod
    def create_upload_record(
        db: Session,
        video_asset_id: str,
        title: str,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        privacy: str = "private",
        category_id: Optional[str] = None,
        job_id: Optional[str] = None,
        upload_mode: str = "upload_now",
        scheduled_at: Optional[datetime] = None,
        scheduled_timezone: Optional[str] = None,
        publish_at: Optional[str] = None,
    ) -> YouTubeUpload:
        """Create a new YouTubeUpload record."""
        record = YouTubeUpload(
            video_asset_id=video_asset_id,
            job_id=job_id,
            title=title[:100],  # YouTube title limit
            description=(description or "")[:5000],
            tags=json.dumps(tags or []),
            privacy=privacy if privacy in ("public", "unlisted", "private") else "private",
            category_id=category_id,
            status="queued",
            upload_mode=upload_mode,
            scheduled_at=scheduled_at,
            scheduled_timezone=scheduled_timezone,
            publish_at=publish_at,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def get_upload(db: Session, upload_id: str) -> Optional[YouTubeUpload]:
        return db.query(YouTubeUpload).filter(YouTubeUpload.id == upload_id).first()

    @staticmethod
    def get_upload_by_job(db: Session, job_id: str) -> Optional[YouTubeUpload]:
        return db.query(YouTubeUpload).filter(YouTubeUpload.job_id == job_id).first()

    @staticmethod
    def get_upload_by_asset(db: Session, asset_id: str) -> Optional[YouTubeUpload]:
        """Return the most recent upload for a video asset."""
        return (
            db.query(YouTubeUpload)
            .filter(YouTubeUpload.video_asset_id == asset_id)
            .order_by(YouTubeUpload.created_at.desc())
            .first()
        )

    @staticmethod
    def check_already_uploaded(db: Session, asset_id: str) -> Optional[str]:
        """
        Return the YouTube video ID if this asset was already successfully uploaded.
        Used to prevent duplicate uploads.
        """
        existing = (
            db.query(YouTubeUpload)
            .filter(
                YouTubeUpload.video_asset_id == asset_id,
                YouTubeUpload.upload_confirmed == "true",
            )
            .first()
        )
        return existing.youtube_video_id if existing else None

    @staticmethod
    def perform_upload(
        db: Session,
        upload_record: YouTubeUpload,
        google_creds,
    ) -> str:
        """
        Perform the actual YouTube upload using resumable upload.

        - For upload_mode='upload_now': uploads and publishes per the privacy setting.
        - For upload_mode='scheduled': uploads as private with publishAt set.

        Updates upload_record status/progress as it goes.
        Returns the YouTube video ID on success.
        Raises RuntimeError on failure.
        """
        from googleapiclient.discovery import build as gapi_build
        from googleapiclient.http import MediaFileUpload
        from googleapiclient.errors import HttpError

        asset = db.query(VideoAsset).filter(
            VideoAsset.id == upload_record.video_asset_id
        ).first()
        if not asset:
            raise RuntimeError(f"Video asset {upload_record.video_asset_id} not found")

        file_path = Path(asset.file_path)
        if not file_path.exists():
            raise RuntimeError(f"Video file not found on disk: {file_path.name}")

        file_size = file_path.stat().st_size

        # Update status
        upload_record.status = "authorizing"
        upload_record.total_bytes = file_size
        db.commit()

        # Build YouTube API client
        youtube = gapi_build("youtube", "v3", credentials=google_creds)

        # Parse tags
        try:
            tags_list = json.loads(upload_record.tags or "[]")
        except Exception:
            tags_list = []

        # Build status object — scheduled always goes private with publishAt
        status_body: dict = {"selfDeclaredMadeForKids": False}

        if upload_record.upload_mode == "scheduled" and upload_record.publish_at:
            # YouTube requires privacyStatus=private when using publishAt
            status_body["privacyStatus"] = "private"
            status_body["publishAt"] = upload_record.publish_at
        else:
            status_body["privacyStatus"] = upload_record.privacy

        body = {
            "snippet": {
                "title": upload_record.title,
                "description": upload_record.description or "",
                "tags": tags_list,
                "categoryId": upload_record.category_id or "22",  # People & Blogs default
            },
            "status": status_body,
        }

        # Resumable MediaFileUpload — does NOT load the file into memory
        media = MediaFileUpload(
            str(file_path),
            mimetype="video/mp4",
            chunksize=CHUNK_SIZE,
            resumable=True,
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        upload_record.status = "uploading"
        db.commit()

        # Execute the upload in chunks
        response = None
        bytes_sent = 0
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    bytes_sent = int(status.resumable_progress)
                    upload_record.bytes_uploaded = bytes_sent
                    db.commit()
                    logger.info(
                        "Upload %s: %d / %d bytes (%.1f%%)",
                        upload_record.id,
                        bytes_sent,
                        file_size,
                        (bytes_sent / file_size * 100) if file_size else 0,
                    )
            except HttpError as e:
                if e.resp.status in (500, 502, 503, 504):
                    logger.warning("Transient YouTube API error %s — retrying chunk", e.resp.status)
                    continue
                raise RuntimeError(f"YouTube API error: {e.resp.status} — {e.content}") from e

        # Upload complete
        youtube_video_id = response.get("id")
        if not youtube_video_id:
            raise RuntimeError("YouTube upload completed but no video ID returned.")

        youtube_url = f"https://www.youtube.com/watch?v={youtube_video_id}"

        # Determine final status
        if upload_record.upload_mode == "scheduled" and upload_record.publish_at:
            final_status = "scheduled"
        else:
            final_status = "completed"

        upload_record.status = final_status
        upload_record.youtube_video_id = youtube_video_id
        upload_record.youtube_url = youtube_url
        upload_record.bytes_uploaded = file_size
        upload_record.upload_confirmed = "true"
        upload_record.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "Upload %s %s → %s",
            upload_record.id,
            final_status,
            youtube_url,
        )
        return youtube_video_id

    @staticmethod
    def reschedule_upload(
        db: Session,
        upload: YouTubeUpload,
        publish_at_utc: str,
        scheduled_at: datetime,
        scheduled_timezone: str,
        google_creds,
    ) -> YouTubeUpload:
        """
        Update the publishAt on an already-uploaded scheduled video.
        Keeps privacy=private.
        """
        from googleapiclient.discovery import build as gapi_build

        if not upload.youtube_video_id:
            raise RuntimeError("Cannot reschedule: video has not been uploaded to YouTube yet.")

        youtube = gapi_build("youtube", "v3", credentials=google_creds)
        youtube.videos().update(
            part="status",
            body={
                "id": upload.youtube_video_id,
                "status": {
                    "privacyStatus": "private",
                    "publishAt": publish_at_utc,
                    "selfDeclaredMadeForKids": False,
                },
            },
        ).execute()

        upload.publish_at = publish_at_utc
        upload.scheduled_at = scheduled_at
        upload.scheduled_timezone = scheduled_timezone
        db.commit()
        db.refresh(upload)
        logger.info("Upload %s rescheduled → %s", upload.id, publish_at_utc)
        return upload

    @staticmethod
    def cancel_schedule(
        db: Session,
        upload: YouTubeUpload,
        google_creds,
    ) -> YouTubeUpload:
        """
        Cancel a scheduled publish: set privacyStatus=private and clear publishAt.
        The YouTube video remains on YouTube as private.
        """
        from googleapiclient.discovery import build as gapi_build

        if not upload.youtube_video_id:
            raise RuntimeError("Cannot cancel: video has not been uploaded to YouTube yet.")

        youtube = gapi_build("youtube", "v3", credentials=google_creds)
        youtube.videos().update(
            part="status",
            body={
                "id": upload.youtube_video_id,
                "status": {
                    "privacyStatus": "private",
                    "selfDeclaredMadeForKids": False,
                },
            },
        ).execute()

        upload.publish_at = None
        upload.scheduled_at = None
        upload.status = "completed"  # keeps the video, just not scheduled anymore
        upload.upload_mode = "upload_now"
        db.commit()
        db.refresh(upload)
        logger.info("Upload %s schedule cancelled → private", upload.id)
        return upload


youtube_upload_service = YouTubeUploadService()
