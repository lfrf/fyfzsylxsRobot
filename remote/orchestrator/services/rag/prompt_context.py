from services.rag.contracts import RagHit, SafetyRoute


class RagPromptContextBuilder:
    def build(self, hits: list[RagHit], *, route: SafetyRoute, max_chars: int) -> str | None:
        if not hits:
            return None

        header = [
            "【知识库参考】",
            "以下片段仅用于支持性心理健康陪伴，不可作为医学诊断或处方依据。",
            f"检索路由: {route.label}; 风险等级: {route.risk_level}",
        ]
        sections: list[str] = ["\n".join(header)]
        remaining = max_chars - len(sections[0])
        for index, hit in enumerate(hits, start=1):
            chunk = hit.chunk
            prefix = (
                f"[KB{index}] id={chunk.chunk_id} topic={chunk.topic} "
                f"risk={chunk.risk_level} source={chunk.source_level} title={chunk.title} score={hit.score:.3f}"
            )
            text = chunk.text.strip()
            section = f"{prefix}\n{text}"
            if len(section) > remaining:
                section = f"{prefix}\n{text[: max(remaining - len(prefix) - 8, 0)]}..."
            if remaining <= 80:
                break
            sections.append(section)
            remaining -= len(section)

        return "\n\n".join(sections).strip()


rag_prompt_context_builder = RagPromptContextBuilder()
