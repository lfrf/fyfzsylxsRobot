from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Response

from services.robot_media_store import robot_media_store


router = APIRouter()


@router.get("/v1/robot/media/tts/{session_id}/{turn_id}.wav")
async def robot_tts_media(session_id: str, turn_id: str) -> Response:
    upstream_url = robot_media_store.get_tts_url(session_id=session_id, turn_id=turn_id)
    if not upstream_url:
        raise HTTPException(status_code=404, detail="TTS media is not registered for this turn.")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            upstream = await client.get(upstream_url)
            upstream.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch upstream TTS media: {exc}") from exc

    return Response(content=upstream.content, media_type="audio/wav")
