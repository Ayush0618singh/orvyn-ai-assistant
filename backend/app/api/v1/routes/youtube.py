
from typing import Any

from fastapi import APIRouter, Query

from app.services.youtube_service import search_youtube_videos

router = APIRouter(prefix="/youtube", tags=["YouTube"])


@router.get("/search")
async def search_videos(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=10),
) -> dict[str, Any]:
    """Search embeddable YouTube videos without exposing the API key."""
    return await search_youtube_videos(q, limit)
