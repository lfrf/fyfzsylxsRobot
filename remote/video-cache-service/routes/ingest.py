from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.buffer import video_buffer

router = APIRouter(prefix="/v1/video", tags=["video"])


class VideoFrameIn(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str | int
    stream_id: str = Field(default="video-001")
    frame_id: int = Field(..., ge=1)
    timestamp_ms: int = Field(..., ge=0)
    width: int = Field(..., ge=1)
    height: int = Field(..., ge=1)
    mime_type: str = Field(default="image/jpeg")
    image_base64: str = Field(..., min_length=1)


class VideoIngestRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    turn_id: str | int
    stream_id: str = Field(default="video-001")
    frames: list[VideoFrameIn] = Field(default_factory=list)


class VideoIngestResponse(BaseModel):
    status: str = "ok"
    received_frames: int
    stored_frames: int
    keys: list[tuple[str, str | int, str]] = Field(default_factory=list)


@router.post("/ingest", response_model=VideoIngestResponse)
async def ingest(request: VideoIngestRequest) -> VideoIngestResponse:
    payload: list[dict[str, Any]] = []
    for frame in request.frames:
        payload.append(frame.model_dump())
    stored = video_buffer.append_many(payload)
    return VideoIngestResponse(
        received_frames=len(request.frames),
        stored_frames=stored,
        keys=video_buffer.list_keys(),
    )