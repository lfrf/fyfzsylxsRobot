import httpx

from config import settings
from models import ChatRequest, VisionFeatures


class VisionClient:
    async def extract_features(self, request: ChatRequest) -> VisionFeatures | None:
        has_video = bool(request.video_frames or request.video_meta)
        if settings.vision_service_enabled and has_video:
            try:
                return await self._call_service(request)
            except httpx.HTTPError:
                pass

        return request.vision_features

    async def _call_service(self, request: ChatRequest) -> VisionFeatures | None:
        payload = {
            "session_id": request.session_id,
            "turn_id": request.turn_id,
            "input_type": request.input_type,
            "video_frames": [
                frame.model_dump() if hasattr(frame, "model_dump") else frame.dict()
                for frame in request.video_frames
            ],
            "video_meta": (
                request.video_meta.model_dump() if request.video_meta and hasattr(request.video_meta, "model_dump")
                else request.video_meta.dict() if request.video_meta
                else None
            ),
            "turn_time_window": (
                request.turn_time_window.model_dump()
                if request.turn_time_window and hasattr(request.turn_time_window, "model_dump")
                else request.turn_time_window.dict() if request.turn_time_window
                else None
            ),
        }

        async with httpx.AsyncClient(timeout=settings.vision_service_timeout_seconds) as client:
            response = await client.post(f"{settings.vision_service_base}/extract", json=payload)
            response.raise_for_status()

        body = response.json()
        if not body.get("vision_features"):
            return None
        return VisionFeatures(**body["vision_features"])


vision_client = VisionClient()
