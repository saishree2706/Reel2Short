"""
YouTube OAuth service.

Handles:
- Building the Google authorization URL with PKCE-like state validation
- Exchanging OAuth code for credentials
- Storing and retrieving credentials from the database
- Automatic token refresh before API calls
- Fetching channel info
- Revoking/disconnecting credentials
"""
import json
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.youtube_credential import YouTubeCredential

logger = logging.getLogger(__name__)

# YouTube Data API v3 — minimum scope for uploading
YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
# Read-only scope to fetch channel info
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"

SCOPES = [YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READONLY_SCOPE]

# Token considered expired if within this many seconds of expiry
_EXPIRY_BUFFER_SECONDS = 300  # 5 minutes


def _get_flow():
    """Build a google_auth_oauthlib Flow from current settings."""
    from google_auth_oauthlib.flow import Flow

    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    return flow


def build_authorization_url(db: Session) -> tuple[str, str]:
    """
    Generate a Google OAuth authorization URL + a random state token.

    Returns (authorization_url, state).
    The state must be stored by the caller (e.g., in session/DB) and
    validated in the callback to prevent CSRF.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env"
        )

    flow = _get_flow()
    state = secrets.token_urlsafe(32)

    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="false",
        prompt="consent",   # force consent so we always get a refresh_token
        state=state,
    )
    return auth_url, state


def handle_oauth_callback(
    db: Session,
    code: str,
    state: str,
    expected_state: str,
) -> YouTubeCredential:
    """
    Exchange the authorization code for credentials.

    Validates state, fetches tokens, fetches channel info,
    upserts a YouTubeCredential row, and returns it.
    """
    # 1. State validation (CSRF protection)
    if not secrets.compare_digest(state, expected_state):
        raise ValueError("OAuth state mismatch — possible CSRF attack.")

    # 2. Exchange code for tokens
    flow = _get_flow()
    flow.fetch_token(code=code)
    google_creds = flow.credentials

    # 3. Fetch channel info
    channel_id, channel_name = _fetch_channel_info(google_creds)

    # 4. Upsert credential record
    cred = _upsert_credential(
        db=db,
        channel_id=channel_id,
        channel_name=channel_name,
        google_creds=google_creds,
    )
    logger.info("YouTube credential stored for channel: %s", channel_name)
    return cred


def _fetch_channel_info(google_creds) -> tuple[str, str]:
    """Fetch the authenticated user's YouTube channel ID and name."""
    from googleapiclient.discovery import build as gapi_build

    try:
        youtube = gapi_build("youtube", "v3", credentials=google_creds)
        resp = youtube.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            return ("unknown", "Unknown Channel")
        item = items[0]
        return item["id"], item["snippet"]["title"]
    except Exception as e:
        logger.warning("Could not fetch channel info: %s", e)
        return ("unknown", "Unknown Channel")


def _upsert_credential(
    db: Session,
    channel_id: str,
    channel_name: str,
    google_creds,
) -> YouTubeCredential:
    """Create or update the single YouTubeCredential record."""
    # We only support one connected channel for the MVP.
    # Use the first existing record if present.
    cred = db.query(YouTubeCredential).first()
    expiry_str = _expiry_to_str(google_creds.expiry)

    if cred is None:
        cred = YouTubeCredential(
            provider="google",
            channel_id=channel_id,
            channel_name=channel_name,
            access_token=google_creds.token,
            refresh_token=google_creds.refresh_token,
            token_expiry=expiry_str,
            scopes=" ".join(google_creds.scopes or SCOPES),
            state="active",
        )
        db.add(cred)
    else:
        cred.channel_id = channel_id
        cred.channel_name = channel_name
        cred.access_token = google_creds.token
        if google_creds.refresh_token:
            cred.refresh_token = google_creds.refresh_token
        cred.token_expiry = expiry_str
        cred.scopes = " ".join(google_creds.scopes or SCOPES)
        cred.state = "active"

    db.commit()
    db.refresh(cred)
    return cred


def get_active_credential(db: Session) -> Optional[YouTubeCredential]:
    """Return the active YouTubeCredential if one exists."""
    return (
        db.query(YouTubeCredential)
        .filter(YouTubeCredential.state == "active")
        .first()
    )


def get_valid_google_credentials(db: Session):
    """
    Return a valid google.oauth2.credentials.Credentials object.

    If the stored access token is near expiry, automatically refreshes it
    and persists the new token to the database.

    Raises RuntimeError if no credential is connected or refresh fails.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    cred = get_active_credential(db)
    if not cred:
        raise RuntimeError("No YouTube account connected.")
    if cred.state != "active":
        raise RuntimeError(
            f"YouTube credential is not active (state: {cred.state}). "
            "Please reconnect your YouTube account."
        )

    google_creds = Credentials(
        token=cred.access_token,
        refresh_token=cred.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=cred.scopes.split() if cred.scopes else SCOPES,
    )

    # Restore expiry from stored string
    if cred.token_expiry:
        google_creds.expiry = _str_to_expiry(cred.token_expiry)

    # Refresh if expired or near-expiry
    if _is_near_expiry(google_creds):
        logger.info("Access token near expiry — refreshing...")
        try:
            google_creds.refresh(Request())
            # Persist refreshed credentials
            cred.access_token = google_creds.token
            cred.token_expiry = _expiry_to_str(google_creds.expiry)
            if google_creds.refresh_token:
                cred.refresh_token = google_creds.refresh_token
            db.commit()
            logger.info("Token refreshed and persisted.")
        except Exception as e:
            cred.state = "expired"
            db.commit()
            raise RuntimeError(
                f"Token refresh failed: {e}. Please reconnect your YouTube account."
            ) from e

    return google_creds


def disconnect(db: Session) -> bool:
    """
    Disconnect YouTube: mark credentials as revoked, attempt Google revocation.
    Returns True if disconnected, False if nothing was connected.
    """
    cred = db.query(YouTubeCredential).first()
    if not cred:
        return False

    # Attempt to revoke with Google (best-effort)
    _try_revoke_token(cred.access_token or cred.refresh_token)

    # Remove locally — clear tokens for safety, mark revoked
    cred.access_token = None
    cred.refresh_token = None
    cred.token_expiry = None
    cred.state = "revoked"
    db.commit()
    logger.info("YouTube credential revoked for channel: %s", cred.channel_name)
    return True


def _try_revoke_token(token: Optional[str]) -> None:
    """Best-effort token revocation with Google."""
    if not token:
        return
    try:
        import httpx
        httpx.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": token},
            timeout=10,
        )
    except Exception as e:
        logger.warning("Could not revoke token with Google: %s", e)


def _is_near_expiry(creds) -> bool:
    """Return True if the access token is expired or will expire within the buffer."""
    if not creds.token:
        return True
    if creds.expired:
        return True
    if creds.expiry:
        remaining = (creds.expiry - datetime.utcnow()).total_seconds()
        return remaining < _EXPIRY_BUFFER_SECONDS
    return False


def _expiry_to_str(expiry) -> Optional[str]:
    """Convert a datetime expiry to an ISO 8601 UTC string."""
    if expiry is None:
        return None
    if hasattr(expiry, "isoformat"):
        return expiry.isoformat()
    return str(expiry)


def _str_to_expiry(expiry_str: str):
    """Parse an ISO 8601 string back to a naive datetime (UTC)."""
    try:
        # Handle both timezone-aware and naive formats
        dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        # google-auth needs a naive UTC datetime
        if dt.tzinfo is not None:
            dt = dt.utctimetuple()
            dt = datetime(*dt[:6])
        return dt
    except Exception:
        return None

