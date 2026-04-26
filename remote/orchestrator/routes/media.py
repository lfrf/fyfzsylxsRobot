import httpx
from fastapi import APIRouter, HTTPException, Response

from config import settings

router = APIRouter()


@router.get("/media/video/{session_id}/{turn_id}")
async def proxy_turn_video(session_id: str, turn_id: int) -> Response:
    media_url = f"{settings.avatar_service_base}/media/video/{session_id}/{turn_id}"
    try:
        async with httpx.AsyncClient(timeout=settings.avatar_service_timeout_seconds) as client:
            upstream = await client.get(media_url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Avatar media fetch failed: {exc}") from exc

    if upstream.status_code == 404:
        raise HTTPException(status_code=404, detail="Reply video not found.")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=502, detail="Avatar media fetch failed.")

    headers = {}
    content_length = upstream.headers.get("content-length")
    if content_length:
        headers["content-length"] = content_length
    headers["cache-control"] = "no-store, no-cache, must-revalidate, max-age=0"
    headers["pragma"] = "no-cache"
    headers["expires"] = "0"

    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "video/mp4"),
        headers=headers,
    )


@router.get("/media/video-chunk/{session_id}/{turn_id}/{chunk_index}")
async def proxy_turn_video_chunk(session_id: str, turn_id: int, chunk_index: int) -> Response:
    media_url = f"{settings.avatar_service_base}/media/video-chunk/{session_id}/{turn_id}/{chunk_index}"
    try:
        async with httpx.AsyncClient(timeout=settings.avatar_service_timeout_seconds) as client:
            upstream = await client.get(media_url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Avatar media fetch failed: {exc}") from exc

    if upstream.status_code == 404:
        raise HTTPException(status_code=404, detail="Reply video chunk not found.")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=502, detail="Avatar media fetch failed.")

    headers = {
        "cache-control": "no-store, no-cache, must-revalidate, max-age=0",
        "pragma": "no-cache",
        "expires": "0",
    }
    content_length = upstream.headers.get("content-length")
    if content_length:
        headers["content-length"] = content_length

    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "video/mp4"),
        headers=headers,
    )


@router.get("/media/video-stream/{session_id}/{turn_id}/manifest")
async def proxy_turn_video_stream_manifest(session_id: str, turn_id: int) -> Response:
    media_url = f"{settings.avatar_service_base}/media/video-stream/{session_id}/{turn_id}/manifest"
    try:
        async with httpx.AsyncClient(timeout=settings.avatar_service_timeout_seconds) as client:
            upstream = await client.get(media_url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Avatar media fetch failed: {exc}") from exc

    if upstream.status_code == 404:
        raise HTTPException(status_code=404, detail="Reply video stream not found.")
    if upstream.status_code >= 400:
        raise HTTPException(status_code=502, detail="Avatar media fetch failed.")

    headers = {
        "cache-control": "no-store, no-cache, must-revalidate, max-age=0",
        "pragma": "no-cache",
        "expires": "0",
    }
    return Response(
        content=upstream.content,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers=headers,
    )
