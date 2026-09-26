"""Instagram API endpoints."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas.instagram import InstagramMediaList, ReelStatusResponse
from ..services.instagram_service import InstagramService
from ..config import settings

router = APIRouter(prefix="/api/instagram", tags=["instagram"])


def _get_service(access_token: Optional[str] = None) -> InstagramService:
    token = access_token or settings.INSTAGRAM_ACCESS_TOKEN
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Instagram access token is not configured. Add INSTAGRAM_ACCESS_TOKEN to .env",
        )
    return InstagramService(access_token=token)


@router.get("/reels", response_model=InstagramMediaList)
async def list_reels(
    cursor: Optional[str] = Query(None, description="Pagination cursor (after)"),
    limit: int = Query(25, ge=1, le=50),
):
    """
    Fetch the authenticated user's Instagram Reels.
    Returns only media where media_type==VIDEO and media_product_type==REELS.
    Supports cursor-based pagination.
    """
    svc = _get_service()
    try:
        return await svc.fetch_reels(after_cursor=cursor, limit=limit)
    except Exception as e:
        _handle_instagram_error(e)


@router.get("/media", response_model=InstagramMediaList)
async def list_media(
    cursor: Optional[str] = Query(None, description="Pagination cursor (after)"),
    limit: int = Query(25, ge=1, le=50),
):
    """Fetch all media (not filtered to Reels)."""
    svc = _get_service()
    try:
        return await svc.fetch_media_page(after_cursor=cursor, limit=limit)
    except Exception as e:
        _handle_instagram_error(e)


@router.get("/reels/{media_id}/status", response_model=ReelStatusResponse)
async def reel_status(media_id: str):
    """
    Check if a specific Reel has a downloadable media_url.
    Returns download_available=false + manual_upload_required=true when not.
    """
    svc = _get_service()
    try:
        media = await svc.get_media_item(media_id)
    except Exception as e:
        _handle_instagram_error(e)

    return ReelStatusResponse(
        media_id=media.id,
        download_available=media.download_available,
        manual_upload_required=not media.download_available,
        media_url=media.media_url,
        thumbnail_url=media.thumbnail_url,
        caption=media.caption,
        timestamp=media.timestamp,
        permalink=media.permalink,
    )


def _handle_instagram_error(exc: Exception) -> None:
    """Convert httpx / API errors into meaningful HTTP responses."""
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text[:300]

        if status in (400, 401, 403):
            raise HTTPException(status_code=status, detail=detail)
        raise HTTPException(status_code=502, detail=f"Instagram API error {status}: {detail}")

    if isinstance(exc, httpx.RequestError):
        raise HTTPException(status_code=503, detail=f"Cannot reach Instagram API: {exc}")

    raise HTTPException(status_code=500, detail=str(exc))

