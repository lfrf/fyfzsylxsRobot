import json

from config import settings
from models import ExtractRequest, ExtractResponse, VideoMeta, VisionFeatures
from services.facial_emotion_runtime import facial_emotion_runtime
from services.qwen_vl_runtime import qwen_vl_runtime
from services.storage import vision_storage
from services.video_ring_buffer import video_ring_buffer


class FrameFeatureExtractor:
    def extract(self, request: ExtractRequest) -> ExtractResponse:
        buffer_frame_count = video_ring_buffer.ingest(
            session_id=request.session_id,
            turn_time_window=request.turn_time_window,
            frames=request.video_frames,
        )
        window_selection = video_ring_buffer.select_window(
            session_id=request.session_id,
            turn_time_window=request.turn_time_window,
            fallback_frames=request.video_frames,
        )

        selected_frames = window_selection.video_frames
        processed_frame_count = len(selected_frames)
        incoming_video_meta = request.video_meta

        if not processed_frame_count and not incoming_video_meta:
            return ExtractResponse(
                vision_features=None,
                video_meta=None,
                processed_frame_count=0,
                extractor_mode=settings.extractor_mode,
            )

        if incoming_video_meta:
            if hasattr(incoming_video_meta, "model_copy"):
                normalized_video_meta = incoming_video_meta.model_copy(deep=True)
            else:
                normalized_video_meta = incoming_video_meta.copy(deep=True)
        else:
            normalized_video_meta = VideoMeta()
        normalized_video_meta.source = normalized_video_meta.source or "browser_camera"
        normalized_video_meta.frame_count = (
            incoming_video_meta.frame_count if incoming_video_meta and incoming_video_meta.frame_count else len(request.video_frames)
        )
        normalized_video_meta.buffered_frame_count = buffer_frame_count
        normalized_video_meta.sampled_frame_count = processed_frame_count
        normalized_video_meta.keyframe_strategy = "remote_ring_window_selection"

        motion_level = "still"
        if processed_frame_count >= 5:
            motion_level = "moderate"
        elif processed_frame_count >= 3:
            motion_level = "low"

        summary_parts = []
        if processed_frame_count:
            summary_parts.append(f"{processed_frame_count} key frames selected")
        if normalized_video_meta and normalized_video_meta.width and normalized_video_meta.height:
            summary_parts.append(f"{normalized_video_meta.width}x{normalized_video_meta.height}")
        summary_parts.append(
            f"window={window_selection.selection_mode}"
            + (
                f"({window_selection.window_started_at_ms}-{window_selection.window_ended_at_ms})"
                if window_selection.window_started_at_ms is not None and window_selection.window_ended_at_ms is not None
                else ""
            )
        )

        if hasattr(request, "model_copy"):
            request_for_model = request.model_copy(update={"video_frames": selected_frames, "video_meta": normalized_video_meta})
        else:
            request_for_model = request.copy(update={"video_frames": selected_frames, "video_meta": normalized_video_meta})

        if settings.extractor_mode == "qwen2_5_vl":
            vision_features = qwen_vl_runtime.extract(request_for_model)
        else:
            vision_features = VisionFeatures(
                scene_summary=", ".join(summary_parts) or "video turn captured",
                attention_target="camera",
                motion_level=motion_level,
                emotion_tags=[],
                source="remote_vision_service",
                frame_count=processed_frame_count or (normalized_video_meta.sampled_frame_count if normalized_video_meta else 0),
            )

        fer_result = facial_emotion_runtime.infer(selected_frames)
        if fer_result:
            merged_emotion_tags = _merge_unique_tags(
                fer_result.emotion_tags,
                vision_features.emotion_tags if vision_features else [],
            )
            if vision_features:
                vision_features.emotion_tags = merged_emotion_tags
                if vision_features.source:
                    vision_features.source = f"{vision_features.source}+{fer_result.source}"
                else:
                    vision_features.source = fer_result.source
            vision_storage.persist_payload(
                session_id=request.session_id,
                turn_id=request.turn_id,
                file_name="face_emotion.json",
                payload={
                    "dominant_emotion": fer_result.dominant_emotion,
                    "emotion_tags": fer_result.emotion_tags,
                    "confidence": fer_result.confidence,
                    "source": fer_result.source,
                    "model_ref": fer_result.model_ref,
                },
            )

        if vision_features:
            base_source = "remote_qwen2_5_vl:ring_window" if settings.extractor_mode == "qwen2_5_vl" else vision_features.source
            if fer_result and fer_result.source and base_source and fer_result.source not in base_source:
                vision_features.source = f"{base_source}+{fer_result.source}"
            else:
                vision_features.source = base_source

        if normalized_video_meta:
            serialized_video_meta = (
                normalized_video_meta.model_dump()
                if hasattr(normalized_video_meta, "model_dump")
                else normalized_video_meta.dict()
            )
            vision_storage.persist_payload(
                session_id=request.session_id,
                turn_id=request.turn_id,
                file_name="video_meta.json",
                payload=json.loads(json.dumps(serialized_video_meta, ensure_ascii=False, default=str)),
            )
        vision_storage.persist_payload(
            session_id=request.session_id,
            turn_id=request.turn_id,
            file_name="window_selection.json",
            payload={
                "selection_mode": window_selection.selection_mode,
                "buffer_frame_count": window_selection.buffer_frame_count,
                "selected_frame_count": processed_frame_count,
                "window_started_at_ms": window_selection.window_started_at_ms,
                "window_ended_at_ms": window_selection.window_ended_at_ms,
            },
        )
        serialized_vision_features = (
            vision_features.model_dump() if hasattr(vision_features, "model_dump") else vision_features.dict()
        )
        vision_storage.persist_payload(
            session_id=request.session_id,
            turn_id=request.turn_id,
            file_name="vision_features.json",
            payload=json.loads(json.dumps(serialized_vision_features, ensure_ascii=False, default=str)),
        )

        return ExtractResponse(
            vision_features=vision_features,
            video_meta=normalized_video_meta,
            processed_frame_count=processed_frame_count,
            extractor_mode=settings.extractor_mode,
        )


def _merge_unique_tags(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    for item in (primary or []) + (secondary or []):
        text = (item or "").strip()
        if text and text not in merged:
            merged.append(text)
    return merged


frame_feature_extractor = FrameFeatureExtractor()
