import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse

from services.storage import avatar_storage

router = APIRouter()


@router.get("/media/video/{session_id}/{turn_id}")
async def get_turn_video(session_id: str, turn_id: int) -> FileResponse:
    video_path = avatar_storage.get_video_path(session_id=session_id, turn_id=turn_id)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Reply video not found.")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"{session_id}-{turn_id}.mp4",
        headers={
            "cache-control": "no-store, no-cache, must-revalidate, max-age=0",
            "pragma": "no-cache",
            "expires": "0",
        },
    )


@router.get("/media/video-chunk/{session_id}/{turn_id}/{chunk_index}")
async def get_turn_video_chunk(session_id: str, turn_id: int, chunk_index: int) -> FileResponse:
    chunk_path = avatar_storage.get_video_chunk_path(
        session_id=session_id,
        turn_id=turn_id,
        chunk_index=chunk_index,
    )
    if not chunk_path.exists():
        raise HTTPException(status_code=404, detail="Reply video chunk not found.")

    return FileResponse(
        path=chunk_path,
        media_type="video/mp4",
        filename=f"{session_id}-{turn_id}-chunk-{chunk_index:04d}.mp4",
        headers={
            "cache-control": "no-store, no-cache, must-revalidate, max-age=0",
            "pragma": "no-cache",
            "expires": "0",
        },
    )


@router.get("/media/video-stream/{session_id}/{turn_id}/manifest")
async def get_turn_video_stream_manifest(session_id: str, turn_id: int) -> JSONResponse:
    manifest_path = avatar_storage.get_video_manifest_path(session_id=session_id, turn_id=turn_id)
    if manifest_path.exists():
        return JSONResponse(json.loads(manifest_path.read_text(encoding="utf-8")))

    # Fallback manifest for single-file mode to keep frontends backward-compatible.
    fallback_video = avatar_storage.get_video_path(session_id=session_id, turn_id=turn_id)
    if not fallback_video.exists():
        raise HTTPException(status_code=404, detail="Reply video stream not found.")

    payload = {
        "session_id": session_id,
        "turn_id": turn_id,
        "chunk_seconds": None,
        "complete": True,
        "chunks": [
            {
                "index": 1,
                "url": f"/media/video/{session_id}/{turn_id}",
            }
        ],
    }
    return JSONResponse(payload)
