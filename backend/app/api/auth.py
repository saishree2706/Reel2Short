"""
Google / YouTube OAuth endpoints.

Routes:
  GET  /api/auth/google/connect   — return authorization URL (no redirect)
  GET  /api/auth/google/callback  — handle OAuth code exchange (browser redirect)
  POST /api/auth/google/disconnect — remove stored credentials
  GET  /api/auth/google/status    — return connection status (no tokens)
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.youtube import YouTubeConnectionStatus
from ..services.youtube_auth_service import (
    build_authorization_url,
    handle_oauth_callback,
    get_active_credential,
    disconnect,
)

router = APIRouter(prefix="/api/auth/google", tags=["auth"])
logger = logging.getLogger(__name__)

# In-memory state store for the OAuth flow.
# For single-user local dev this is sufficient.
# Production: use a proper server-side session or short-lived DB record.
_pending_oauth_states: dict[str, str] = {}


@router.get("/connect")
def start_google_oauth(db: Session = Depends(get_db)):
    """
    Return the Google authorization URL for the frontend to redirect to.
    Response: {"auth_url": "https://accounts.google.com/..."}
    """
    try:
        auth_url, state = build_authorization_url(db)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    _pending_oauth_states["current"] = state
    return {"auth_url": auth_url}


@router.get("/callback")
def google_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Google redirects here after the user grants/denies permission.
    On success: redirect to frontend with ?connected=1
    On error: redirect to frontend with ?error=...
    """
    # User denied access
    if error:
        logger.warning("OAuth error from Google: %s", error)
        return RedirectResponse(
            url=f"http://localhost:5173/youtube/connect?error={error}",
            status_code=302,
        )

    if not code or not state:
        return RedirectResponse(
            url="http://localhost:5173/youtube/connect?error=missing_params",
            status_code=302,
        )

    expected_state = _pending_oauth_states.get("current", "")
    _pending_oauth_states.pop("current", None)

    try:
        handle_oauth_callback(db, code=code, state=state, expected_state=expected_state)
    except ValueError as e:
        logger.error("OAuth state mismatch: %s", e)
        return RedirectResponse(
            url="http://localhost:5173/youtube/connect?error=state_mismatch",
            status_code=302,
        )
    except Exception as e:
        logger.error("OAuth callback failed: %s", e)
        return RedirectResponse(
            url=f"http://localhost:5173/youtube/connect?error=callback_failed",
            status_code=302,
        )

    return RedirectResponse(
        url="http://localhost:5173/youtube/connect?connected=1",
        status_code=302,
    )


@router.get("/status", response_model=YouTubeConnectionStatus)
def youtube_connection_status(db: Session = Depends(get_db)):
    """Return YouTube connection status without exposing tokens."""
    cred = get_active_credential(db)
    if not cred:
        return YouTubeConnectionStatus(connected=False)
    return YouTubeConnectionStatus(
        connected=True,
        channel_id=cred.channel_id,
        channel_name=cred.channel_name,
        state=cred.state,
    )


@router.post("/disconnect")
def disconnect_youtube(db: Session = Depends(get_db)):
    """
    Revoke and remove YouTube credentials.
    Best-effort Google revocation — does not fail if Google is unreachable.
    """
    disconnected = disconnect(db)
    if not disconnected:
        raise HTTPException(status_code=404, detail="No YouTube account connected.")
    return {"message": "YouTube account disconnected successfully."}

