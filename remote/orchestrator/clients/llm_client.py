from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import httpx

from config import settings
from logging_utils import get_active_log_session_id, log_event
from services.mode_policy import ModePolicy
from services.rag_router import RagRoute


@dataclass(frozen=True)
class LLMResult:
    reply_text: str
    source: str
    reasoning_hint: str | None = None
    latency_ms: float | None = None
    fallback: bool = False
    service_url: str | None = None


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
        service_url = f"{self.api_base}/chat/completions" if self.api_base else None
        log_event(
            "llm_request_started",
            api_base=self.api_base,
            model=self.model,
            mode=mode_policy.mode_id,
            active_rag_namespace=rag_route.namespace,
            asr_text=asr_text,
            mock_enabled=self.use_mock or settings.llm_provider == "mock",
        )
        started = perf_counter()
        system_prompt = self._build_system_prompt(mode_policy, rag_route, rag_context)
        self._log_prompt_built(
            mode_policy=mode_policy,
            rag_context=rag_context,
            system_prompt=system_prompt,
        )
        if self.use_mock or not self.api_base or settings.llm_provider == "mock":
            result = self._mock_result(
                asr_text=asr_text,
                mode_policy=mode_policy,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=True,
                service_url=service_url,
            )
            self._log_result(result)
            return result

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
            "X-Robot-Log-Session-Id": get_active_log_session_id(),
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(service_url, headers=headers, json=payload)
                response.raise_for_status()
            body = response.json()
            reply_text = body["choices"][0]["message"]["content"].strip()
            result = LLMResult(
                reply_text=reply_text,
                source="qwen_vllm",
                reasoning_hint="live-openai-compatible",
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=False,
                service_url=service_url,
            )
            self._log_result(result)
            return result
        except Exception as exc:
            fallback = self._mock_result(
                asr_text=asr_text,
                mode_policy=mode_policy,
                latency_ms=round((perf_counter() - started) * 1000, 2),
                fallback=True,
                service_url=service_url,
            )
            result = LLMResult(
                reply_text=fallback.reply_text,
                source=f"fallback:qwen_vllm:{type(exc).__name__}",
                reasoning_hint=str(exc),
                latency_ms=fallback.latency_ms,
                fallback=True,
                service_url=service_url,
            )
            self._log_result(result)
            return result

    def _build_system_prompt(self, mode_policy: ModePolicy, rag_route: RagRoute, rag_context: str | None) -> str:
        parts = [
            settings.system_prompt,
            mode_policy.system_instruction,
        ]
        if mode_policy.few_shots:
            parts.append(f”## 示例\n{mode_policy.few_shots}”)
        if mode_policy.output_constraints:
            parts.append(f”## 输出约束\n{mode_policy.output_constraints}”)
        parts.extend([
            (
                “【语音输出约束】\n”
                “1. 你的回复会被直接 TTS 播放。\n”
                “2. 不要使用 Markdown。\n”
                “3. 不要使用表格。\n”
                “4. 不要使用长列表。\n”
                “5. 不要输出括号里的舞台说明。\n”
                “6. 不要说”作为一个 AI”。\n”
                “7. care/accompany/game 模式通常不超过 120 个汉字。\n”
                “8. learning 模式可以稍长，但也要分层清楚、适合语音播放。\n”
                “9. 每次回复尽量只完成一个主要意图。\n”
                “10. 除非用户要求详细解释，否则不要长篇展开。”
            ),
            f”Current robot mode: {mode_policy.mode_id}.”,
            f”Display mode name: {mode_policy.display_name}.”,
            f”Speech style: {mode_policy.speech_style}.”,
            f”Active RAG namespace: {rag_route.namespace}.”,
            “Your answer will be spoken by a desktop robot, so keep it natural and not too long.”,
            “Answer in concise spoken Chinese unless the user asks otherwise.”,
            “Do not mention avatar, video rendering, lip-sync, or digital human output.”,
        ])
        if rag_context:
            parts.append(f”Optional retrieved context:\n{rag_context}”)
        return “\n”.join(parts)

    def _mock_result(
        self,
        *,
        asr_text: str,
        mode_policy: ModePolicy,
        latency_ms: float | None,
        fallback: bool,
        service_url: str | None,
    ) -> LLMResult:
        if asr_text == "mock audio received":
            return LLMResult(
                reply_text=mode_policy.normal_reply,
                source="mock",
                reasoning_hint="audio-placeholder",
                latency_ms=latency_ms,
                fallback=fallback,
                service_url=service_url,
            )
        return LLMResult(
            reply_text=f"{mode_policy.normal_reply} 你刚才说的是：{asr_text}",
            source="mock",
            reasoning_hint="echo-with-mode-policy",
            latency_ms=latency_ms,
            fallback=fallback,
            service_url=service_url,
        )

    def _log_result(self, result: LLMResult) -> None:
        log_event(
            "llm_result",
            reply_text=result.reply_text,
            source=result.source,
            latency_ms=result.latency_ms,
            fallback=result.fallback,
        )

    def _log_prompt_built(
        self,
        *,
        mode_policy: ModePolicy,
        rag_context: str | None,
        system_prompt: str,
    ) -> None:
        prompt_sections = [
            "settings_system_prompt",
            "mode_instruction",
        ]
        if mode_policy.few_shots:
            prompt_sections.append("mode_few_shots")
        if mode_policy.output_constraints:
            prompt_sections.append("mode_output_constraints")
        prompt_sections.extend([
            "tts_output_constraints",
            "mode_metadata",
        ])
        if rag_context:
            prompt_sections.append("rag_context")
        log_event(
            "llm_prompt_built",
            mode=mode_policy.mode_id,
            display_name=mode_policy.display_name,
            instruction_chars=len(mode_policy.system_instruction or ""),
            few_shots_chars=len(mode_policy.few_shots or ""),
            output_constraints_chars=len(mode_policy.output_constraints or ""),
            rag_context_used=bool(rag_context),
            rag_context_chars=len(rag_context or ""),
            speech_style=mode_policy.speech_style,
            prompt_chars=len(system_prompt),
            prompt_sections=prompt_sections,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )


llm_client = LLMClient()

__all__ = ["LLMClient", "LLMResult", "llm_client"]
