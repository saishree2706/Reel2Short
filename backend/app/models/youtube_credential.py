"""YouTubeCredential — stores OAuth tokens for the connected YouTube account."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, String, Text
from ..database import Base


class YouTubeCredential(Base):
    __tablename__ = "youtube_credentials"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # OAuth provider (always "google" for YouTube)
    provider = Column(String, nullable=False, default="google")

    # YouTube channel info (populated after first successful auth)
    channel_id = Column(String, nullable=True, index=True)
    channel_name = Column(String, nullable=True)

    # OAuth tokens — never returned via API
    # Access token expires; refresh token is long-lived
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)

    # ISO 8601 UTC string of when the access token expires
    token_expiry = Column(String, nullable=True)

    # Scopes granted
    scopes = Column(Text, nullable=True)  # space-separated

    # Connection state: "active" | "revoked" | "expired"
    state = Column(String, nullable=False, default="active")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

