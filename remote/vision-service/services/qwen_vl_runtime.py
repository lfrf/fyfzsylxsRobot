import base64
import json
import re
from io import BytesIO
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

from config import settings
from models import ExtractRequest, VisionFeatures
from services.storage import vision_storage


def _resolve_torch_dtype(dtype_name: str) -> torch.dtype:
    if dtype_name == "bfloat16":
        return torch.bfloat16
    if dtype_name == "float32":
        return torch.float32
    return torch.float16


class QwenVLRuntime:
    def __init__(self) -> None:
        self._processor = None
        self._model = None
        self._device = settings.vision_device

    def warmup(self) -> None:
        if not settings.vision_warmup_enabled:
            return
        try:
            self._ensure_runtime()
        except Exception:
            # Keep the service alive even if the heavyweight runtime is not ready.
            pass

    def extract(self, request: ExtractRequest) -> VisionFeatures | None:
        frames = request.video_frames
        if not frames:
            return None

        try:
            return self._extract_with_model(request)
        except Exception as exc:
            fallback = VisionFeatures(
                scene_summary=f"video turn captured; remote vision fallback ({type(exc).__name__})",
                attention_target="camera",
                motion_level="unknown",
                emotion_tags=[],
                source="remote_qwen_vl_fallback",
                frame_count=len(frames),
            )
            vision_storage.persist_payload(
                session_id=request.session_id,
                turn_id=request.turn_id,
                file_name="vision_runtime_error.json",
                payload={
                    "error_type": type(exc).__name__,
                    "detail": str(exc),
                },
            )
            return fallback

    def _extract_with_model(self, request: ExtractRequest) -> VisionFeatures:
        processor, model = self._ensure_runtime()
        images = [self._decode_frame(frame.image_base64) for frame in request.video_frames if frame.image_base64]
        if not images:
            raise ValueError("No decodable image frames were provided.")

        prompt = self._build_prompt(request, len(images))
        messages = [
            {
                "role": "user",
                "content": [
                    *({"type": "image"} for _ in images),
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        chat_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(
            text=[chat_text],
            images=images,
            padding=True,
            return_tensors="pt",
        )
        model_inputs = {
            key: value.to(self._device) if isinstance(value, torch.Tensor) else value
            for key, value in inputs.items()
        }
        generated_ids = model.generate(**model_inputs, max_new_tokens=settings.vision_max_new_tokens)
        generated_trimmed = [
            output_ids[len(input_ids) :]
            for input_ids, output_ids in zip(model_inputs["input_ids"], generated_ids, strict=False)
        ]
        raw_output = processor.batch_decode(
            generated_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        parsed = self._parse_json(raw_output)
        vision_features = VisionFeatures(
            scene_summary=parsed.get("scene_summary") or "visual scene observed",
            attention_target=parsed.get("attention_target") or "camera",
            motion_level=parsed.get("motion_level") or "unknown",
            emotion_tags=[str(tag) for tag in parsed.get("emotion_tags", []) if str(tag).strip()],
            source="remote_qwen2_5_vl",
            frame_count=len(images),
        )

        vision_storage.persist_payload(
            session_id=request.session_id,
            turn_id=request.turn_id,
            file_name="vision_prompt.json",
            payload={
                "prompt": prompt,
                "frame_count": len(images),
                "capture_strategy": request.turn_time_window.capture_strategy if request.turn_time_window else None,
            },
        )
        serialized_features = vision_features.model_dump() if hasattr(vision_features, "model_dump") else vision_features.dict()
        vision_storage.persist_payload(
            session_id=request.session_id,
            turn_id=request.turn_id,
            file_name="vision_features.json",
            payload=serialized_features,
        )
        vision_storage.persist_payload(
            session_id=request.session_id,
            turn_id=request.turn_id,
            file_name="vision_raw_output.json",
            payload={
                "raw_output": raw_output,
                "parsed_output": parsed,
            },
        )
        return vision_features

    def _ensure_runtime(self):
        if self._processor is not None and self._model is not None:
            return self._processor, self._model

        torch_dtype = _resolve_torch_dtype(settings.vision_dtype)
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            settings.vision_model,
            torch_dtype=torch_dtype,
            trust_remote_code=True,
        )
        processor = AutoProcessor.from_pretrained(settings.vision_model, trust_remote_code=True)
        model.to(self._device)
        model.eval()

        self._processor = processor
        self._model = model
        return processor, model

    def _decode_frame(self, image_base64: str) -> Image.Image:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(BytesIO(image_bytes))
        return image.convert("RGB")

    def _build_prompt(self, request: ExtractRequest, frame_count: int) -> str:
        width = request.video_meta.width if request.video_meta else None
        height = request.video_meta.height if request.video_meta else None
        trigger_note = None
        if request.turn_time_window:
            trigger_note = {
                "capture_strategy": request.turn_time_window.capture_strategy,
                "triggered_at_ms": request.turn_time_window.triggered_at_ms,
                "pre_roll_ms": request.turn_time_window.pre_roll_ms,
                "post_roll_ms": request.turn_time_window.post_roll_ms,
            }

        prompt_payload = {
            "task": (
                "You are the visual preprocessing module for an emotional support digital human system. "
                "Analyze the provided event-window keyframes and respond with strict JSON."
            ),
            "output_format": {
                "scene_summary": "short text",
                "attention_target": "camera|screen|downward|sideward|unknown",
                "motion_level": "still|low|moderate|high",
                "emotion_tags": ["calm", "fatigued", "tense", "sad", "neutral"],
            },
            "input_context": {
                "frame_count": frame_count,
                "resolution": f"{width}x{height}" if width and height else None,
                "input_type": request.input_type,
                "trigger_window": trigger_note,
            },
            "rules": [
                "Return JSON only.",
                "Use conservative wording when uncertain.",
                "Base the answer only on visible posture, gaze, facial tension, and motion.",
            ],
        }
        return json.dumps(prompt_payload, ensure_ascii=False)

    def _parse_json(self, raw_output: str) -> dict:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
            cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))


qwen_vl_runtime = QwenVLRuntime()
