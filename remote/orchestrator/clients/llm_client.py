from __future__ import annotations

from dataclasses import dataclass

import httpx

from config import settings
from services.mode_policy import ModePolicy
from services.rag_router import RagRoute


@dataclass(frozen=True)
class LLMResult:
    reply_text: str
    source: str
    reasoning_hint: str | None = None


class LLMClient:
    def __init__(
        self,
        *,
        api_base: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        use_mock: bool | None = None,
    ) -> None:
        self.api_base = (api_base or settings.llm_api_base).rstrip("/")
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.llm_api_key
        self.timeout_seconds = timeout_seconds or settings.llm_request_timeout_seconds
        self.use_mock = settings.robot_chat_use_mock_llm if use_mock is None else use_mock

    def generate_reply(
        self,
        *,
        session_id: str,
        turn_id: str,
        asr_text: str,
        mode_policy: ModePolicy,
        rag_route: RagRoute,
        rag_context: str | None = None,
    ) -> LLMResult:
        if self.use_mock or not self.api_base or settings.llm_provider == "mock":
            return self._mock_result(asr_text=asr_text, mode_policy=mode_policy)

        system_prompt = self._build_system_prompt(mode_policy, rag_route, rag_context)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": asr_text},
            ],
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.api_base}/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
            body = response.json()
            reply_text = body["choices"][0]["message"]["content"].strip()
            return LLMResult(reply_text=reply_text, source="qwen_vllm", reasoning_hint="live-openai-compatible")
        except Exception as exc:
            fallback = self._mock_result(asr_text=asr_text, mode_policy=mode_policy)
            return LLMResult(
                reply_text=fallback.reply_text,
                source=f"fallback:qwen_vllm:{type(exc).__name__}",
                reasoning_hint=str(exc),
            )

    def _build_system_prompt(self, mode_policy: ModePolicy, rag_route: RagRoute, rag_context: str | None) -> str:
        parts = [
            settings.system_prompt,
            f"Current robot mode: {mode_policy.mode_id}.",
            f"Speech style: {mode_policy.speech_style}.",
            f"Active RAG namespace: {rag_route.namespace}.",
            "Answer in concise spoken Chinese unless the user asks otherwise.",
            "Do not mention avatar, video rendering, lip-sync, or digital human output.",
        ]
        if rag_context:
            parts.append(f"Optional retrieved context:\n{rag_context}")
        return "\n".join(parts)

    def _mock_result(self, *, asr_text: str, mode_policy: ModePolicy) -> LLMResult:
        if asr_text == "mock audio received":
            return LLMResult(
                reply_text=mode_policy.normal_reply,
                source="mock",
                reasoning_hint="audio-placeholder",
            )
        return LLMResult(
            reply_text=f"{mode_policy.normal_reply} 你刚才说的是：{asr_text}",
            source="mock",
            reasoning_hint="echo-with-mode-policy",
        )


llm_client = LLMClient()

__all__ = ["LLMClient", "LLMResult", "llm_client"]
