from __future__ import annotations

import importlib
import math
import struct
import sys
import wave
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from config import settings
from models import TTSRequest, TTSResponse
from services.storage import speech_storage


class TTSService:
    def __init__(self) -> None:
        self._model = None

    def warmup(self) -> None:
        if settings.tts_warmup_enabled and settings.tts_provider not in {"mock", "placeholder"}:
            self._ensure_model()

    def synthesize(self, request: TTSRequest) -> TTSResponse:
        text = self._sanitize(request.text)
        if not text:
            return TTSResponse(type="none", audio_url=None, source="empty_text")

        try:
            if settings.tts_provider in {"mock", "placeholder"}:
                audio_bytes, sample_rate = self._mock_wav(text)
                source = "mock_tts"
            else:
                audio_bytes, sample_rate = self._run_cosyvoice(request, text)
                source = f"speech_service_{settings.tts_provider}"
        except Exception:
            if not settings.tts_allow_mock_fallback:
                raise
            audio_bytes, sample_rate = self._mock_wav(text)
            source = f"fallback_mock_tts:{settings.tts_provider}"

        speech_storage.persist_tts_audio(
            session_id=request.session_id,
            turn_id=request.turn_id,
            audio_bytes=audio_bytes,
        )
        duration_ms = self._duration_ms(audio_bytes)
        audio_url = self._build_audio_url(request.session_id, request.turn_id)
        return TTSResponse(
            type="audio_url",
            audio_url=audio_url,
            format="wav",
            duration_ms=duration_ms,
            sample_rate=sample_rate,
            source=source,
            model_ref=settings.tts_model,
            device=settings.tts_device,
        )

    def get_audio_path(self, *, session_id: str, turn_id: str) -> Path:
        return speech_storage.get_tts_audio_path(session_id=session_id, turn_id=turn_id)

    def _sanitize(self, text: str) -> str:
        return (text or "").replace("*", "").strip()

    def _build_audio_url(self, session_id: str, turn_id: str) -> str:
        safe_session = quote(session_id, safe="")
        safe_turn = quote(turn_id, safe="")
        path = f"/tts/audio/{safe_session}/{safe_turn}.wav"
        if settings.speech_public_base_url:
            return f"{settings.speech_public_base_url}{path}"
        return path

    def _ensure_model(self):
        if self._model is not None:
            return self._model

        self._extend_sys_path_from_repo()
        module = importlib.import_module("cosyvoice.cli.cosyvoice")
        auto_model = getattr(module, "AutoModel")
        self._model = auto_model(model_dir=settings.tts_model)
        return self._model

    def _extend_sys_path_from_repo(self) -> None:
        if not settings.tts_repo_path:
            return
        repo_path = Path(settings.tts_repo_path).expanduser()
        matcha_path = repo_path / "third_party" / "Matcha-TTS"
        for candidate in (repo_path, matcha_path):
            if candidate.exists() and str(candidate) not in sys.path:
                sys.path.append(str(candidate))

    def _run_cosyvoice(self, request: TTSRequest, text: str) -> tuple[bytes, int]:
        model = self._ensure_model()
        speed = request.speed or settings.tts_speed
        speaker_id = request.speaker_id or settings.tts_speaker_id
        sample_rate = int(getattr(model, "sample_rate", settings.tts_sample_rate))

        if settings.tts_mode == "cosyvoice_300m_instruct":
            outputs = self._invoke_300m_instruct(model, text, request.speech_style, speed=speed, speaker_id=speaker_id)
        elif hasattr(model, "inference_sft") and speaker_id:
            outputs = model.inference_sft(text, speaker_id, stream=False, speed=speed)
        elif hasattr(model, "inference"):
            outputs = model.inference(text=text, stream=False, speed=speed)
        elif hasattr(model, "inference_tts"):
            outputs = model.inference_tts(text=text, stream=False, speed=speed)
        else:
            raise RuntimeError("Loaded CosyVoice model exposes no supported inference method.")

        samples = self._collect_samples(outputs)
        return self._samples_to_wav(samples, sample_rate), sample_rate

    def _invoke_300m_instruct(self, model, text: str, speech_style: str, *, speed: float, speaker_id: str | None):
        instruct_text = self._style_to_instruction(speech_style)
        method = getattr(model, "inference_instruct", None) or getattr(model, "inference_instruct2", None)
        if callable(method):
            kwargs = {"tts_text": text, "instruct_text": instruct_text, "stream": False, "speed": speed}
            if speaker_id:
                kwargs["spk_id"] = speaker_id
            try:
                return method(**kwargs)
            except TypeError:
                return method(text, instruct_text, stream=False, speed=speed)
        if hasattr(model, "inference_sft") and speaker_id:
            return model.inference_sft(text, speaker_id, stream=False, speed=speed)
        raise RuntimeError("CosyVoice instruct mode is unavailable for the loaded model.")

    def _style_to_instruction(self, speech_style: str) -> str:
        if speech_style == "care_gentle":
            return "用温和、清楚、稍慢的语气说话。"
        if speech_style == "game_playful":
            return "用轻松、有趣、有互动感的语气说话。"
        if speech_style == "learning_focused":
            return "用清晰、有条理、鼓励学习的语气说话。"
        return "用自然、温暖的语气说话。"

    def _collect_samples(self, outputs) -> list[float]:
        samples: list[float] = []
        for item in outputs:
            speech = item.get("tts_speech") if isinstance(item, dict) else None
            if speech is None:
                continue
            if hasattr(speech, "detach"):
                values = speech.squeeze().detach().cpu().float().numpy().tolist()
            elif hasattr(speech, "tolist"):
                values = speech.squeeze().tolist()
            else:
                values = list(speech)
            if isinstance(values, (int, float)):
                values = [float(values)]
            samples.extend(float(value) for value in values)
        if not samples:
            raise RuntimeError("TTS model returned no audio samples.")
        return samples

    def _mock_wav(self, text: str) -> tuple[bytes, int]:
        sample_rate = settings.tts_sample_rate
        duration_seconds = min(max(len(text) * 0.08, 0.6), 4.0)
        total = int(sample_rate * duration_seconds)
        samples = [0.12 * math.sin(2 * math.pi * 440.0 * index / sample_rate) for index in range(total)]
        return self._samples_to_wav(samples, sample_rate), sample_rate

    def _samples_to_wav(self, samples: list[float], sample_rate: int) -> bytes:
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            frames = bytearray()
            for sample in samples:
                clipped = max(-1.0, min(1.0, float(sample)))
                frames.extend(struct.pack("<h", int(clipped * 32767)))
            wav.writeframes(bytes(frames))
        return buffer.getvalue()

    def _duration_ms(self, audio_bytes: bytes) -> int | None:
        try:
            with wave.open(BytesIO(audio_bytes), "rb") as wav:
                return int(wav.getnframes() * 1000 / wav.getframerate())
        except Exception:
            return None


tts_service = TTSService()

__all__ = ["TTSService", "tts_service"]
