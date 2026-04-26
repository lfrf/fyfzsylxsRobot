from dataclasses import dataclass, field
from typing import Any


MetadataValue = str | int | float | bool | list[str] | None


@dataclass(frozen=True)
class RagDocument:
    doc_id: str
    file_name: str
    title: str
    text: str
    source_path: str
    metadata: dict[str, MetadataValue]


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    doc_id: str
    title: str
    text: str
    source_path: str
    metadata: dict[str, MetadataValue]
    file_name: str = ""
    section_path: list[str] = field(default_factory=list)
    chunk_type: str = "knowledge_fact"
    char_count: int = 0
    chunk_index: int = 0
    total_chunks_in_doc: int = 0

    @property
    def topic(self) -> str:
        raw_topic = str(self.metadata.get("primary_topic") or self.metadata.get("topic") or "general")
        topic_aliases = {
            "safety_rule": "escalation",
            "dialogue_strategy": "support_strategy",
            "older_adult_support": "elderly_support",
            "family_guidance": "elderly_support",
        }
        return topic_aliases.get(raw_topic, raw_topic)

    @property
    def risk_level(self) -> str:
        raw_level = str(self.metadata.get("risk_level") or "low")
        if raw_level == "critical":
            return "high"
        return raw_level

    @property
    def source_level(self) -> str:
        raw_level = self.metadata.get("source_level")
        if raw_level:
            return str(raw_level)
        if self.chunk_type == "safety_rule" or self.topic == "escalation":
            return "safety"
        if self.chunk_type in {"faq", "support_template"}:
            return "dialogue"
        return "core"

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "file_name": self.file_name,
            "title": self.title,
            "section_path": self.section_path,
            "chunk_type": self.chunk_type,
            "text": self.text,
            "char_count": self.char_count or len(self.text),
            "source_path": self.source_path,
            "metadata": self.metadata,
            "chunk_index": self.chunk_index,
            "total_chunks_in_doc": self.total_chunks_in_doc,
        }

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> "RagChunk":
        return cls(
            chunk_id=item["chunk_id"],
            doc_id=item["doc_id"],
            title=item["title"],
            text=item["text"],
            source_path=item.get("source_path") or item.get("metadata", {}).get("source_path") or "",
            metadata=item.get("metadata") or {},
            file_name=item.get("file_name") or "",
            section_path=[str(value) for value in item.get("section_path", [])],
            chunk_type=item.get("chunk_type") or "knowledge_fact",
            char_count=int(item.get("char_count") or len(item["text"])),
            chunk_index=int(item.get("chunk_index") or 0),
            total_chunks_in_doc=int(item.get("total_chunks_in_doc") or 0),
        )


@dataclass(frozen=True)
class RagHit:
    chunk: RagChunk
    score: float


@dataclass(frozen=True)
class SafetyRoute:
    label: str
    risk_level: str
    topics: list[str] = field(default_factory=list)
    source_levels: list[str] = field(default_factory=list)
    should_retrieve: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class RagResult:
    enabled: bool
    query: str
    route: SafetyRoute
    hits: list[RagHit] = field(default_factory=list)
    prompt_context: str | None = None
    error: str | None = None

    @property
    def topics(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for hit in self.hits:
            topic = hit.chunk.topic
            if topic not in seen:
                ordered.append(topic)
                seen.add(topic)
        return ordered

    def build_reasoning_hint(self) -> str:
        top_score = self.hits[0].score if self.hits else 0.0
        topics = ",".join(self.topics[:4]) or "-"
        base = (
            f"route={self.route.label}|risk={self.route.risk_level}|"
            f"rag_hits={len(self.hits)}|topics={topics}|top_score={top_score:.3f}"
        )
        if self.error:
            safe_error = self.error.replace("|", " ")[:80]
            return f"{base}|rag_error={safe_error}"
        return base
