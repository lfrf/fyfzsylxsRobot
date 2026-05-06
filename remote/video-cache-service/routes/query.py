from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from services.buffer import video_buffer

router = APIRouter(prefix="/v1/video", tags=["video"])


class VideoFrameOut(BaseModel):
    session_id: str
    turn_id: str | int
    stream_id: str
    frame_id: int
    timestamp_ms: int
    width: int
    height: int
    mime_type: str
    image_base64: str


class VideoMetaOut(BaseModel):
    frame_count: int = Field(default=0, ge=0)
    first_timestamp_ms: int | None = Field(default=None, ge=0)
    last_timestamp_ms: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)


class VideoQueryResponse(BaseModel):
    session_id: str
    turn_id: str | int
    stream_id: str
    video_meta: VideoMetaOut
    frames: list[VideoFrameOut] = Field(default_factory=list)


@router.get("/query", response_model=VideoQueryResponse)
async def query_video(
    session_id: str = Query(..., min_length=1),
    turn_id: str | int = Query(...),
    stream_id: str = Query(..., min_length=1),
) -> VideoQueryResponse:
    frames = video_buffer.query_frames(session_id=session_id, turn_id=turn_id, stream_id=stream_id)
    if frames:
        first_ts = min(frame.timestamp_ms for frame in frames)
        last_ts = max(frame.timestamp_ms for frame in frames)
        first_width = frames[0].width
        first_height = frames[0].height
        duration_ms = max(0, last_ts - first_ts)
        meta = VideoMetaOut(
            frame_count=len(frames),
            first_timestamp_ms=first_ts,
            last_timestamp_ms=last_ts,
            duration_ms=duration_ms,
            width=first_width,
            height=first_height,
        )
    else:
        meta = VideoMetaOut(frame_count=0)
    return VideoQueryResponse(
        session_id=session_id,
        turn_id=turn_id,
        stream_id=stream_id,
        video_meta=meta,
        frames=[VideoFrameOut(**frame.model_dump()) for frame in frames],
    )