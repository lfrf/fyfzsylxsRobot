import json
import math
import re
from collections import Counter
from pathlib import Path

from services.rag.contracts import RagChunk, RagHit


_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_LATIN_RE = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    lowered = text.lower()
    tokens = _LATIN_RE.findall(lowered)
    for block in _CJK_RE.findall(lowered):
        tokens.extend(block)
        tokens.extend(block[index : index + 2] for index in range(0, max(len(block) - 1, 0)))
        tokens.extend(block[index : index + 3] for index in range(0, max(len(block) - 2, 0)))
    return [token for token in tokens if token.strip()]


class RagIndex:
    def __init__(self, chunks: list[RagChunk] | None = None) -> None:
        self.chunks = chunks or []
        self._chunk_vectors: list[Counter[str]] = []
        self._idf: dict[str, float] = {}
        self._build_lexical_stats()

    @property
    def ready(self) -> bool:
        return bool(self.chunks)

    @classmethod
    def load(cls, index_dir: str | Path) -> "RagIndex | None":
        chunk_path = Path(index_dir).expanduser() / "chunks.jsonl"
        if not chunk_path.exists():
            return None

        chunks: list[RagChunk] = []
        with chunk_path.open("r", encoding="utf-8") as input_file:
            for line in input_file:
                if not line.strip():
                    continue
                item = json.loads(line)
                chunks.append(RagChunk.from_dict(item))
        return cls(chunks)

    def save(self, index_dir: str | Path) -> None:
        root = Path(index_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        with (root / "chunks.jsonl").open("w", encoding="utf-8") as output_file:
            for chunk in self.chunks:
                output_file.write(json.dumps(chunk.to_dict(), ensure_ascii=False))
                output_file.write("\n")
        with (root / "index_meta.json").open("w", encoding="utf-8") as output_file:
            json.dump(
                {
                    "backend": "lexical_tfidf",
                    "chunk_count": len(self.chunks),
                    "source": "processed/chunks.jsonl",
                },
                output_file,
                ensure_ascii=False,
                indent=2,
            )

    def search(
        self,
        query: str,
        *,
        top_k: int,
        min_score: float,
        topics: list[str] | None = None,
        source_levels: list[str] | None = None,
        risk_level: str | None = None,
    ) -> list[RagHit]:
        if not self.chunks or not query.strip():
            return []

        query_vector = self._weight_vector(Counter(tokenize(query)))
        if not query_vector:
            return []

        topic_set = {item for item in (topics or []) if item}
        source_set = {item for item in (source_levels or []) if item}
        scored: list[RagHit] = []
        for chunk, raw_vector in zip(self.chunks, self._chunk_vectors, strict=False):
            if risk_level != "high" and chunk.risk_level == "high":
                continue
            if topic_set and chunk.topic not in topic_set and chunk.source_level != "dialogue":
                continue
            chunk_vector = self._weight_vector(raw_vector)
            score = self._cosine(query_vector, chunk_vector)
            score *= self._metadata_boost(chunk, topic_set=topic_set, source_set=source_set, risk_level=risk_level)
            if score >= min_score:
                scored.append(RagHit(chunk=chunk, score=round(score, 4)))

        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_k]

    def _build_lexical_stats(self) -> None:
        self._chunk_vectors = []
        document_frequency: Counter[str] = Counter()
        for chunk in self.chunks:
            metadata_text = " ".join(
                str(value) if not isinstance(value, list) else " ".join(str(item) for item in value)
                for value in chunk.metadata.values()
            )
            vector = Counter(tokenize(f"{chunk.title}\n{metadata_text}\n{chunk.text}"))
            self._chunk_vectors.append(vector)
            document_frequency.update(vector.keys())

        total = max(len(self.chunks), 1)
        self._idf = {
            token: math.log((total + 1) / (frequency + 0.5)) + 1.0
            for token, frequency in document_frequency.items()
        }

    def _weight_vector(self, vector: Counter[str]) -> dict[str, float]:
        return {
            token: count * self._idf.get(token, 1.0)
            for token, count in vector.items()
            if token
        }

    def _cosine(self, left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        shared = set(left) & set(right)
        numerator = sum(left[token] * right[token] for token in shared)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm <= 0 or right_norm <= 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _metadata_boost(
        self,
        chunk: RagChunk,
        *,
        topic_set: set[str],
        source_set: set[str],
        risk_level: str | None,
    ) -> float:
        boost = 1.0
        if topic_set and chunk.topic in topic_set:
            boost += 0.25
        if source_set and chunk.source_level in source_set:
            boost += 0.15
        if risk_level and chunk.risk_level == risk_level:
            boost += 0.1
        if risk_level == "high" and chunk.source_level == "safety":
            boost += 0.3
        return boost
