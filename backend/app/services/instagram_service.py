"""Instagram API service — fetches and normalizes media from the Graph API."""
import httpx
from typing import Optional

from ..schemas.instagram import InstagramMedia, InstagramMediaList
from ..config import settings

_BASE_URL = "https://graph.instagram.com/v21.0"

# Fields requested from the Instagram API
_MEDIA_FIELDS = "id,media_type,media_product_type,media_url,thumbnail_url,permalink,caption,timestamp"


class InstagramService:
    def __init__(self, access_token: Optional[str] = None) -> None:
        self.access_token = access_token or settings.INSTAGRAM_ACCESS_TOKEN

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _params(self, **extra) -> dict:
        return {"access_token": self.access_token, **extra}

    async def _get(self, path: str, params: dict) -> dict:
        """Perform an authenticated GET request."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{_BASE_URL}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_user_id(self) -> str:
        """Return the authenticated user's Instagram user ID."""
        data = await self._get("/me", self._params(fields="id,username"))
        return data["id"]

    async def fetch_media_page(
        self,
        user_id: Optional[str] = None,
        after_cursor: Optional[str] = None,
        limit: int = 25,
    ) -> InstagramMediaList:
        """
        Fetch one page of the user's media.

        - If user_id is None, fetches from /me/media.
        - Supports pagination via after_cursor.
        """
        path = f"/{user_id}/media" if user_id else "/me/media"
        params = self._params(fields=_MEDIA_FIELDS, limit=limit)
        if after_cursor:
            params["after"] = after_cursor

        data = await self._get(path, params)

        raw_items = data.get("data", [])
        paging = data.get("paging", {})
        cursors = paging.get("cursors", {})
        next_cursor = cursors.get("after")

        items = [self._normalize(item) for item in raw_items]

        return InstagramMediaList(
            items=items,
            next_cursor=next_cursor,
            has_more=bool(next_cursor),
        )

    async def fetch_reels(
        self,
        after_cursor: Optional[str] = None,
        limit: int = 25,
    ) -> InstagramMediaList:
        """Fetch media and filter to Reels only."""
        page = await self.fetch_media_page(after_cursor=after_cursor, limit=limit)
        reels = [item for item in page.items if item.is_reel]
        return InstagramMediaList(
            items=reels,
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        )

    async def fetch_all_reels(self, max_pages: int = 10) -> list[InstagramMedia]:
        """Fetch all reels up to max_pages pages."""
        all_reels: list[InstagramMedia] = []
        cursor = None
        for _ in range(max_pages):
            page = await self.fetch_reels(after_cursor=cursor)
            all_reels.extend(page.items)
            if not page.has_more:
                break
            cursor = page.next_cursor
        return all_reels

    async def get_media_item(self, media_id: str) -> InstagramMedia:
        """Fetch a single media item by ID."""
        data = await self._get(f"/{media_id}", self._params(fields=_MEDIA_FIELDS))
        return self._normalize(data)

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(raw: dict) -> InstagramMedia:
        """Convert a raw API dict into a typed InstagramMedia object."""
        return InstagramMedia(
            id=raw.get("id", ""),
            media_type=raw.get("media_type", ""),
            media_product_type=raw.get("media_product_type"),
            media_url=raw.get("media_url"),
            thumbnail_url=raw.get("thumbnail_url"),
            permalink=raw.get("permalink"),
            caption=raw.get("caption"),
            timestamp=raw.get("timestamp"),
        )


# Module-level singleton (uses token from .env by default)
instagram_service = InstagramService()

