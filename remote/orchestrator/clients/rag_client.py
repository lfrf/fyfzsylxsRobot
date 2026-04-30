from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from logging_utils import log_event


CARE_DEFAULT_DOCS = (
    "00_care_mode_principles.md",
    "99_forbidden_medical_claims.md",
)

CARE_PRIORITY_RULES = (
    (
        ("累", "困", "疲惫"),
        (
            "02_daily_life_reminders.md",
            "05_sleep_and_rest_support.md",
            "01_emotional_comfort_phrases.md",
        ),
    ),
    (
        ("头晕", "胸口痛", "呼吸困难", "摔倒", "不舒服"),
        (
            "03_elderly_safety_boundaries.md",
            "99_forbidden_medical_claims.md",
        ),
    ),
    (
        ("孤独", "无聊", "没人陪"),
        (
            "04_loneliness_and_companionship.md",
            "01_emotional_comfort_phrases.md",
        ),
    ),
)


@dataclass(frozen=True)
class RetrievedChunk:
    path: str
    score: int
    content: str


class RAGClient:
    def __init__(self, *, knowledge_base_root: str | None = None, max_chars: int = 2400) -> None:
        orchestrator_root = Path(__file__).resolve().parents[1]
        self.knowledge_base_root = Path(
            knowledge_base_root
            or os.getenv("RAG_KNOWLEDGE_BASE_ROOT", "")
            or orchestrator_root / "knowledge_base"
        )
        self.max_chars = max_chars
        self.last_matched_files: list[str] = []
        self.last_used_default_docs = False
        self.last_context_chars = 0

    def retrieve_context(self, *, namespace: str, query: str) -> str | None:
        raw_namespace = namespace
        self._reset_last_result()
        log_event(
            "rag_retrieve_started",
            namespace=raw_namespace,
            query=query,
            knowledge_base_root=str(self.knowledge_base_root),
        )
        namespace = self._normalize_namespace(namespace)
        if not namespace:
            log_event("rag_namespace_missing", namespace=raw_namespace, namespace_dir="")
            return self._finish_retrieve(namespace=raw_namespace, query=query, context=None)

        namespace_dir = self.knowledge_base_root / namespace
        if not self._is_safe_child(namespace_dir, self.knowledge_base_root):
            log_event("rag_namespace_missing", namespace=namespace, namespace_dir=str(namespace_dir))
            return self._finish_retrieve(namespace=namespace, query=query, context=None)
        if not namespace_dir.exists() or not namespace_dir.is_dir():
            log_event("rag_namespace_missing", namespace=namespace, namespace_dir=str(namespace_dir))
            return self._finish_retrieve(namespace=namespace, query=query, context=None)

        docs = sorted(namespace_dir.glob("*.md"))
        if not docs:
            return self._finish_retrieve(namespace=namespace, query=query, context=None)

        chunks = self._rank_docs(docs, query, namespace=namespace)

        if not chunks and namespace == "care":
            chunks = self._default_care_docs(namespace_dir)
            self.last_used_default_docs = bool(chunks)

        if not chunks:
            return self._finish_retrieve(namespace=namespace, query=query, context=None)

        selected_text = []
        total = 0
        for chunk in chunks[:3]:
            block = f"【来源：{Path(chunk.path).name}】\n{chunk.content.strip()}"
            if total + len(block) > self.max_chars:
                block = block[: max(0, self.max_chars - total)]
            selected_text.append(block)
            total += len(block)
            if total >= self.max_chars:
                break

        self.last_matched_files = [Path(chunk.path).name for chunk in chunks[: len(selected_text)]]
        context = "\n\n---\n\n".join(selected_text).strip() or None
        return self._finish_retrieve(namespace=namespace, query=query, context=context)

    def _rank_docs(self, docs: list[Path], query: str, *, namespace: str) -> list[RetrievedChunk]:
        query_tokens = self._tokens(query)
        doc_scores: dict[Path, int] = {}

        for path in docs:
            text = path.read_text(encoding="utf-8", errors="ignore")
            score = self._score(text, query_tokens)
            if score > 0:
                doc_scores[path] = score

        if namespace == "care":
            for index, path in enumerate(self._care_priority_docs(docs, query)):
                # Priority matches should outrank incidental keyword matches while
                # still allowing matched content order to remain deterministic.
                doc_scores[path] = max(doc_scores.get(path, 0), 100 - index)

        chunks = [
            RetrievedChunk(
                path=str(path),
                score=score,
                content=path.read_text(encoding="utf-8", errors="ignore"),
            )
            for path, score in doc_scores.items()
        ]
        chunks.sort(key=lambda x: (-x.score, Path(x.path).name))
        return chunks

    def _care_priority_docs(self, docs: list[Path], query: str) -> list[Path]:
        by_name = {path.name: path for path in docs}
        selected: list[Path] = []
        for keywords, names in CARE_PRIORITY_RULES:
            if any(keyword in query for keyword in keywords):
                for name in names:
                    path = by_name.get(name)
                    if path and path not in selected:
                        selected.append(path)
        return selected

    def _default_care_docs(self, namespace_dir: Path) -> list[RetrievedChunk]:
        chunks = []
        for name in CARE_DEFAULT_DOCS:
            path = namespace_dir / name
            if path.exists():
                chunks.append(
                    RetrievedChunk(
                        path=str(path),
                        score=1,
                        content=path.read_text(encoding="utf-8", errors="ignore"),
                    )
                )
        return chunks

    def _tokens(self, query: str) -> set[str]:
        base_tokens = set(re.findall(r"[\u4e00-\u9fff]{1,4}|[a-zA-Z0-9]+", query.lower()))

        # care 模式常见语义扩展
        expansions = {
            "累": {"疲惫", "休息", "喝水", "安抚"},
            "困": {"睡眠", "休息", "疲惫"},
            "孤独": {"陪伴", "聊天", "家人"},
            "无聊": {"陪伴", "聊天"},
            "头晕": {"安全", "医生", "家人"},
            "胸口": {"安全", "医生", "紧急"},
            "睡不着": {"睡眠", "休息", "放松"},
            "不舒服": {"安全", "医生", "家人"},
        }

        for key, values in expansions.items():
            if key in query:
                base_tokens.update(values)

        return base_tokens

    def _score(self, text: str, query_tokens: set[str]) -> int:
        lowered = text.lower()
        return sum(lowered.count(token.lower()) for token in query_tokens if token)

    def _normalize_namespace(self, namespace: str) -> str:
        namespace = (namespace or "").strip()
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", namespace):
            return ""
        return namespace

    def _is_safe_child(self, child: Path, parent: Path) -> bool:
        try:
            child.resolve().relative_to(parent.resolve())
            return True
        except ValueError:
            return False

    def _reset_last_result(self) -> None:
        self.last_matched_files = []
        self.last_used_default_docs = False
        self.last_context_chars = 0

    def _finish_retrieve(self, *, namespace: str, query: str, context: str | None) -> str | None:
        self.last_context_chars = len(context or "")
        log_event(
            "rag_retrieve_finished",
            namespace=namespace,
            query=query,
            matched_files=self.last_matched_files,
            context_chars=self.last_context_chars,
            used_default_docs=self.last_used_default_docs,
            max_chars=self.max_chars,
        )
        return context


rag_client = RAGClient()

__all__ = ["RAGClient", "rag_client"]
