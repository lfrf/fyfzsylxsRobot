from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

from config import settings
from models import FaceIdentityResponse, FaceIdentityRequest
from services.face_identity_service import face_identity_service

router = APIRouter()


class VideoCacheQueryRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str | int
    stream_id: str = Field(..., min_length=1)


class CacheIdentityResponse(BaseModel):
    cache_query: dict[str, Any] | None = None
    face_identity: FaceIdentityResponse | None = None


@router.post("/v1/vision/identity/from-cache", response_model=CacheIdentityResponse)
async def extract_face_identity_from_cache(request: VideoCacheQueryRequest) -> CacheIdentityResponse:
    query_url = f"{settings.video_cache_base_url.rstrip('/')}/v1/video/query"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            query_url,
            params={
                "session_id": request.session_id,
                "turn_id": request.turn_id,
                "stream_id": request.stream_id,
            },
        )
        response.raise_for_status()
        cache_data = response.json()

    frames = cache_data.get("frames") or []
    # frame_id from video-cache-service is int; VideoFrameSchema expects str
    normalized_frames = [
        {**frame, "frame_id": str(frame["frame_id"])} if isinstance(frame.get("frame_id"), int) else frame
        for frame in frames
    ]
    face_request = FaceIdentityRequest(
        session_id=request.session_id,
        turn_id=request.turn_id,
        video_frames=normalized_frames,
        video_meta=cache_data.get("video_meta"),
    )
    identity_result = face_identity_service.extract_identity(face_request)
    return CacheIdentityResponse(cache_query=cache_data, face_identity=identity_result)
