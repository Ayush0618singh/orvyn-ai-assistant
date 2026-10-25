
import asyncio
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import HTTPException, status

load_dotenv()

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def _search_youtube_sync(query: str, max_results: int) -> dict[str, Any]:
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YouTube API is not configured on the server.",
        )

    params = urlencode(
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "videoEmbeddable": "true",
            "maxResults": max_results,
            "safeSearch": "moderate",
            "regionCode": "IN",
            "key": api_key,
        }
    )

    try:
        with urlopen(f"{YOUTUBE_SEARCH_URL}?{params}", timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))

    except HTTPError as exc:
        if exc.code == 403:
            raise HTTPException(
                status_code=502,
                detail=(
                    "YouTube rejected the request. Check API restrictions "
                    "and quota in Google Cloud Console."
                ),
            ) from exc

        raise HTTPException(
            status_code=502,
            detail=f"YouTube API returned HTTP {exc.code}.",
        ) from exc

    except (URLError, TimeoutError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to YouTube. Please try again.",
        ) from exc

    videos: list[dict[str, str]] = []

    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})

        if not video_id:
            continue

        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (
            thumbnails.get("high")
            or thumbnails.get("medium")
            or thumbnails.get("default")
            or {}
        )

        videos.append(
            {
                "video_id": video_id,
                "title": snippet.get("title", "Untitled video"),
                "channel_title": snippet.get("channelTitle", "Unknown channel"),
                "description": snippet.get("description", ""),
                "thumbnail_url": thumbnail.get("url", ""),
                "published_at": snippet.get("publishedAt", ""),
                "watch_url": f"https://www.youtube.com/watch?v={video_id}",
                "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
            }
        )

    return {"query": query, "count": len(videos), "videos": videos}


async def search_youtube_videos(
    query: str,
    max_results: int = 10,
) -> dict[str, Any]:
    cleaned_query = " ".join(query.split())

    if not cleaned_query:
        raise HTTPException(
            status_code=422,
            detail="Search query cannot be empty.",
        )

    if len(cleaned_query) > 200:
        raise HTTPException(
            status_code=422,
            detail="Search query must be 200 characters or fewer.",
        )

    return await asyncio.to_thread(
        _search_youtube_sync,
        cleaned_query,
        max(1, min(max_results, 10)),
    )
