from __future__ import annotations

import re

from config import settings
from logging_utils import log_event


class RAGContextController:
    """Compress retrieved RAG text into mode-aware guidance."""

    def compress(
        self,
        mode_id: str,
        rag_context: str | None,
        *,
        strategy_id: str | None = None,
        max_chars: int | None = None,
    ) -> str | None:
        if not rag_context:
            return None
        if mode_id != "care" or not settings.care_rag_structured_guidance:
            limit = max_chars or self._limit_for_mode(mode_id)
            return self._truncate(rag_context, limit)

        limit = max_chars or settings.care_rag_max_chars
        key_points = self._extract_key_points(rag_context, limit=5)
        guidance_lines = [
            "Care guidance:",
            f"- strategy: {strategy_id or 'general_support'}",
        ]
        if key_points:
            guidance_lines.append("- key_points: " + "；".join(key_points[:4]))
        guidance_lines.append("- risk_boundary: 不做医疗诊断；高风险身体或自伤表达时提醒联系家人、医生或紧急服务。")
        guidance_lines.append("- avoid: 不复制大段安慰话术；不要连续重复喝水、休息、我在这里陪你。")
        final = self._truncate("\n".join(guidance_lines), limit)
        log_event(
            "rag_context_compressed",
            mode_id=mode_id,
            strategy_id=strategy_id,
            rag_original_chars=len(rag_context),
            rag_final_chars=len(final),
            max_chars=limit,
        )
        return final

    def _limit_for_mode(self, mode_id: str) -> int:
        return {
            "care": settings.care_rag_max_chars,
            "accompany": 1000,
            "learning": 1600,
            "game": 800,
        }.get(mode_id, 1000)

    def _extract_key_points(self, text: str, *, limit: int) -> list[str]:
        cleaned = re.sub(r"【来源：.*?】", "", text)
        parts = re.split(r"[\n。！？；;]+", cleaned)
        points: list[str] = []
        for part in parts:
            line = part.strip(" -\t\r")
            if not line or len(line) < 6:
                continue
            if line in points:
                continue
            points.append(line[:80])
            if len(points) >= limit:
                break
        return points

    def _truncate(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max(0, max_chars - 1)].rstrip() + "…"


rag_context_controller = RAGContextController()
