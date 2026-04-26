import json
import re
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from services.rag.contracts import MetadataValue, RagChunk, RagDocument


DEFAULT_METADATA: dict[str, MetadataValue] = {
    "category": "knowledge",
    "primary_topic": "general",
    "secondary_topics": [],
    "scene_types": ["support"],
    "risk_level": "low",
    "applicable_users": ["general_user"],
    "language": "zh-CN",
    "version": "v1",
    "status": "active",
    "source_type": "internal_curated",
    "source_name": "A22 internal curated knowledge",
    "source_authority": "internal",
    "retrieval_priority": "medium",
    "chunk_strategy": "heading_semantic",
}

REQUIRED_METADATA_KEYS = {"id", "title"}
MIN_CHARS = 60
MAX_CHARS = 600


class RagLoader:
    def __init__(self) -> None:
        self.invalid_records: list[str] = []

    def load_documents(self, kb_dir: str | Path) -> list[RagDocument]:
        self.invalid_records = []
        root = Path(kb_dir).expanduser()
        if not root.exists():
            self.invalid_records.append(f"WARN missing kb_dir: {root}")
            return []

        documents: list[RagDocument] = []
        for path in sorted(root.rglob("*.md")):
            if self._should_skip_path(path):
                continue

            text = path.read_text(encoding="utf-8").strip()
            if not text:
                self.invalid_records.append(f"WARN empty document skipped: {path}")
                continue

            metadata, body = self._parse_front_matter(text)
            if not metadata:
                self.invalid_records.append(f"WARN missing front matter skipped: {path}")
                continue

            missing_keys = sorted(key for key in REQUIRED_METADATA_KEYS if not metadata.get(key))
            if missing_keys:
                self.invalid_records.append(f"WARN missing metadata {missing_keys} skipped: {path}")
                continue

            normalized_metadata = self._normalize_metadata(metadata, path)
            if str(normalized_metadata.get("status") or "active").lower() not in {"active", "enabled"}:
                self.invalid_records.append(f"WARN inactive document skipped: {path}")
                continue

            doc_id = str(normalized_metadata["id"])
            title = str(normalized_metadata["title"])
            documents.append(
                RagDocument(
                    doc_id=doc_id,
                    file_name=path.name,
                    title=title,
                    text=body.strip(),
                    source_path=str(path),
                    metadata={**normalized_metadata, "source_path": str(path), "file_name": path.name},
                )
            )
        return documents

    def build_chunks(
        self,
        documents: list[RagDocument],
        *,
        min_chars: int = MIN_CHARS,
        max_chars: int = MAX_CHARS,
    ) -> list[RagChunk]:
        all_chunks: list[RagChunk] = []
        for document in documents:
            doc_chunks: list[RagChunk] = []
            sections = self._split_semantic_sections(document.text)
            for section_path, section_text in sections:
                for piece in self._split_section_text(section_text, max_chars=max_chars):
                    if not piece.strip():
                        continue
                    if len(piece.strip()) < min_chars and doc_chunks:
                        previous = doc_chunks[-1]
                        merged_text = f"{previous.text}\n\n{piece.strip()}"
                        doc_chunks[-1] = replace(
                            previous,
                            text=merged_text,
                            char_count=len(merged_text),
                            metadata={**previous.metadata, "char_count": len(merged_text)},
                        )
                        continue
                    metadata = self._chunk_metadata(document.metadata, section_path, piece)
                    chunk_index = len(doc_chunks) + 1
                    chunk_id = f"{document.doc_id}::chunk::{chunk_index:04d}"
                    doc_chunks.append(
                        RagChunk(
                            chunk_id=chunk_id,
                            doc_id=document.doc_id,
                            title=document.title,
                            text=piece.strip(),
                            source_path=document.source_path,
                            metadata=metadata,
                            file_name=document.file_name,
                            section_path=section_path,
                            chunk_type=str(metadata.get("chunk_type") or "knowledge_fact"),
                            char_count=len(piece.strip()),
                            chunk_index=chunk_index,
                        )
                    )

            total = len(doc_chunks)
            all_chunks.extend(replace(chunk, total_chunks_in_doc=total) for chunk in doc_chunks)
        return all_chunks

    def write_processed(self, kb_dir: str | Path, processed_dir: str | Path) -> tuple[list[RagDocument], list[RagChunk]]:
        documents = self.load_documents(kb_dir)
        chunks = self.build_chunks(documents)

        root = Path(processed_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        chunks_path = root / "chunks.jsonl"
        with chunks_path.open("w", encoding="utf-8") as output_file:
            for chunk in chunks:
                output_file.write(json.dumps(chunk.to_dict(), ensure_ascii=False))
                output_file.write("\n")

        stats = self._build_stats(documents, chunks)
        with (root / "chunk_stats.json").open("w", encoding="utf-8") as output_file:
            json.dump(stats, output_file, ensure_ascii=False, indent=2)

        with (root / "invalid_docs.log").open("w", encoding="utf-8") as output_file:
            for record in self.invalid_records:
                output_file.write(record)
                output_file.write("\n")

        return documents, chunks

    def load_processed_chunks(self, processed_dir: str | Path) -> list[RagChunk]:
        chunks_path = Path(processed_dir).expanduser() / "chunks.jsonl"
        if not chunks_path.exists():
            return []

        chunks: list[RagChunk] = []
        with chunks_path.open("r", encoding="utf-8") as input_file:
            for line in input_file:
                if line.strip():
                    chunks.append(RagChunk.from_dict(json.loads(line)))
        return chunks

    def _should_skip_path(self, path: Path) -> bool:
        name = path.name.lower()
        if name.startswith("readme"):
            return True
        if name.startswith("."):
            return True
        return False

    def _parse_front_matter(self, text: str) -> tuple[dict[str, MetadataValue], str]:
        if not text.startswith("---"):
            return {}, text

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, flags=re.DOTALL)
        if not match:
            return {}, text

        metadata: dict[str, MetadataValue] = {}
        current_list_key: str | None = None
        for raw_line in match.group(1).splitlines():
            line = raw_line.rstrip()
            if not line.strip() or line.strip().startswith("#"):
                continue
            if line.lstrip().startswith("- ") and current_list_key:
                value = line.split("- ", 1)[1].strip()
                existing = metadata.setdefault(current_list_key, [])
                if isinstance(existing, list) and value:
                    existing.append(value.strip('"\''))
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_list_key = key if not value else None
            if not value:
                metadata[key] = []
            elif value.startswith("[") and value.endswith("]"):
                metadata[key] = [
                    item.strip().strip('"\'')
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
            else:
                metadata[key] = value.strip('"\'')

        return metadata, match.group(2)

    def _normalize_metadata(self, metadata: dict[str, MetadataValue], path: Path) -> dict[str, MetadataValue]:
        primary_topic = str(metadata.get("primary_topic") or metadata.get("topic") or "general")
        primary_topic = self._infer_primary_topic(primary_topic, path)
        scene_types = self._as_list(metadata.get("scene_types") or metadata.get("scene") or "support")
        applicable_users = self._as_list(
            metadata.get("applicable_users") or metadata.get("intended_for") or "general_user"
        )
        keywords = self._as_list(metadata.get("keywords") or metadata.get("tags") or [])
        risk_level = str(metadata.get("risk_level") or "low")
        if risk_level == "critical":
            risk_level = "high"

        normalized = {
            **DEFAULT_METADATA,
            **metadata,
            "id": str(metadata.get("id")),
            "title": str(metadata.get("title")),
            "category": self._infer_category(metadata, path),
            "primary_topic": primary_topic,
            "secondary_topics": self._infer_secondary_topics(metadata, path, primary_topic),
            "scene_types": scene_types,
            "risk_level": risk_level,
            "applicable_users": applicable_users,
            "language": self._normalize_language(str(metadata.get("language") or DEFAULT_METADATA["language"])),
            "source_type": str(metadata.get("source_type") or metadata.get("source") or "internal_curated"),
            "source_name": str(metadata.get("source_name") or "A22 internal curated knowledge"),
            "source_authority": str(metadata.get("source_authority") or "internal"),
            "keywords": keywords,
            "retrieval_priority": str(metadata.get("retrieval_priority") or metadata.get("priority") or "medium"),
            "chunk_strategy": str(metadata.get("chunk_strategy") or "heading_semantic"),
        }
        normalized["source_level"] = self._infer_source_level(normalized)
        return normalized

    def _infer_primary_topic(self, topic: str, path: Path) -> str:
        name = path.stem
        if topic == "faq":
            if "anxiety" in name:
                return "anxiety"
            if "depression" in name:
                return "depression"
            if "sleep" in name:
                return "sleep"
            if "risk" in name or "escalation" in name:
                return "escalation"
        if topic == "safety_rule":
            if "mania" in name:
                return "bipolar_risk"
            if "insomnia" in name:
                return "sleep"
            return "escalation"
        if topic == "dialogue_strategy":
            return "support_strategy"
        if topic == "older_adult_support":
            return "elderly_support"
        if topic == "family_guidance":
            return "elderly_support"
        return topic

    def _infer_secondary_topics(
        self,
        metadata: dict[str, MetadataValue],
        path: Path,
        primary_topic: str,
    ) -> list[str]:
        topics = self._as_list(metadata.get("secondary_topics"))
        name = path.stem
        if "sleep" in name and "sleep" not in topics and primary_topic != "sleep":
            topics.append("sleep")
        if "stress" in name and "stress" not in topics and primary_topic != "stress":
            topics.append("stress")
        if "anxiety" in name and "anxiety" not in topics and primary_topic != "anxiety":
            topics.append("anxiety")
        if "escalation" in name and "escalation" not in topics and primary_topic != "escalation":
            topics.append("escalation")
        return topics

    def _infer_category(self, metadata: dict[str, MetadataValue], path: Path) -> str:
        topic = str(metadata.get("primary_topic") or metadata.get("topic") or "")
        style = str(metadata.get("style") or "")
        name = path.stem
        if "safety" in name or topic == "safety_rule" or style == "safety":
            return "safety"
        if name.startswith("faq_") or topic == "faq":
            return "faq"
        if name.startswith("support_templates") or style == "dialogue":
            return "dialogue"
        return str(metadata.get("category") or "knowledge")

    def _infer_source_level(self, metadata: dict[str, MetadataValue]) -> str:
        category = str(metadata.get("category") or "")
        style = str(metadata.get("style") or "")
        scene_types = set(self._as_list(metadata.get("scene_types")))
        if category == "safety" or style == "safety" or "escalation" in scene_types:
            return "safety"
        if category in {"dialogue", "faq"} or style == "dialogue":
            return "dialogue"
        return "core"

    def _normalize_language(self, language: str) -> str:
        if language.lower() in {"zh", "cn", "zh_cn"}:
            return "zh-CN"
        return language

    def _split_semantic_sections(self, text: str) -> list[tuple[list[str], str]]:
        sections: list[tuple[list[str], str]] = []
        current_lines: list[str] = []
        current_path: list[str] = []
        heading_stack: list[tuple[int, str]] = []

        for line in text.splitlines():
            heading = self._parse_heading(line)
            if heading and heading[0] in {2, 3}:
                if current_lines:
                    sections.append((current_path[:], "\n".join(current_lines).strip()))
                    current_lines = []
                level, title = heading
                heading_stack = [(item_level, item_title) for item_level, item_title in heading_stack if item_level < level]
                heading_stack.append((level, title))
                current_path = [item_title for _, item_title in heading_stack]
            current_lines.append(line)

        if current_lines:
            sections.append((current_path[:], "\n".join(current_lines).strip()))

        return [(path, section) for path, section in sections if section]

    def _split_section_text(self, text: str, *, max_chars: int) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        pieces: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(paragraph[offset : offset + max_chars] for offset in range(0, len(paragraph), max_chars))
                continue
            candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(candidate) > max_chars and current:
                pieces.append(current)
                current = paragraph
            else:
                current = candidate
        if current:
            pieces.append(current)
        return pieces

    def _chunk_metadata(
        self,
        document_metadata: dict[str, MetadataValue],
        section_path: list[str],
        text: str,
    ) -> dict[str, MetadataValue]:
        chunk_type = self._infer_chunk_type(document_metadata, section_path, text)
        return {
            **document_metadata,
            "section_path": section_path,
            "chunk_type": chunk_type,
            "char_count": len(text.strip()),
            "is_safety_related": chunk_type == "safety_rule" or str(document_metadata.get("risk_level")) == "high",
        }

    def _infer_chunk_type(
        self,
        metadata: dict[str, MetadataValue],
        section_path: list[str],
        text: str,
    ) -> str:
        category = str(metadata.get("category") or "")
        source_level = str(metadata.get("source_level") or "")
        style = str(metadata.get("style") or "")
        heading = " ".join(section_path)
        if category == "safety" or source_level == "safety" or "升级" in heading or "触发" in heading:
            return "safety_rule"
        if category == "faq" or heading.startswith("示例") or "答题思路" in text:
            return "faq"
        if category == "dialogue" or style == "dialogue" or "模板" in heading:
            return "support_template"
        if any(keyword in heading for keyword in ["建议", "支持", "回答", "应对", "系统动作"]):
            return "support_guidance"
        return "knowledge_fact"

    def _parse_heading(self, line: str) -> tuple[int, str] | None:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
        if not match:
            return None
        return len(match.group(1)), match.group(2).strip()

    def _as_list(self, value: MetadataValue | Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        return [text] if text else []

    def _build_stats(self, documents: list[RagDocument], chunks: list[RagChunk]) -> dict[str, Any]:
        return {
            "doc_count": len(documents),
            "chunk_count": len(chunks),
            "by_primary_topic": dict(Counter(chunk.topic for chunk in chunks)),
            "by_chunk_type": dict(Counter(chunk.chunk_type for chunk in chunks)),
            "by_risk_level": dict(Counter(chunk.risk_level for chunk in chunks)),
            "by_source_level": dict(Counter(chunk.source_level for chunk in chunks)),
            "invalid_record_count": len(self.invalid_records),
        }


rag_loader = RagLoader()
