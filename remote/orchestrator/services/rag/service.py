from pathlib import Path
from threading import Lock

from config import settings
from services.rag.contracts import RagResult, SafetyRoute
from services.rag.index import RagIndex
from services.rag.loader import rag_loader
from services.rag.prompt_context import rag_prompt_context_builder
from services.rag.retriever import rag_retriever


TOPIC_QUERY_EXPANSIONS = {
    "anxiety": "焦虑 紧张 担心 心慌 恐慌 不安 放松 呼吸",
    "depression": "抑郁 情绪低落 难过 没兴趣 绝望 无力 价值感",
    "bipolar_risk": "双相风险 亢奋 精力异常 睡很少也不困 冲动 情绪波动",
    "sleep": "睡眠 失眠 睡不着 早醒 作息 多天没睡",
    "stress": "压力 崩溃 撑不住 学业 工作 照护压力",
    "emotion_regulation": "情绪调节 烦躁 放松 呼吸 正念 行为激活",
    "elderly_support": "老年 孤独 陪伴 家属 照护",
    "support_strategy": "共情 澄清 鼓励 陪伴 安慰 怎么说",
    "escalation": "高风险 自伤 轻生 自杀 伤害自己 紧急服务 求助 家属 专业人员",
}


class RagService:
    def __init__(self) -> None:
        self._index: RagIndex | None = None
        self._lock = Lock()

    def ensure_ready(self) -> RagIndex | None:
        if self._index is not None:
            return self._index

        with self._lock:
            if self._index is not None:
                return self._index

            if not settings.rag_rebuild_on_start:
                self._index = RagIndex.load(settings.rag_index_dir)

            if self._index is None:
                chunks = self._load_or_build_processed_chunks()
                self._index = RagIndex(chunks)
                if chunks:
                    self._index.save(settings.rag_index_dir)

        return self._index

    def rebuild_index(self) -> RagIndex:
        with self._lock:
            chunks = self._load_or_build_processed_chunks(force_rebuild=True)
            self._index = RagIndex(chunks)
            Path(settings.rag_index_dir).expanduser().mkdir(parents=True, exist_ok=True)
            self._index.save(settings.rag_index_dir)
            return self._index

    def retrieve(self, *, query: str, route: SafetyRoute) -> RagResult:
        if not settings.rag_enabled:
            return RagResult(enabled=False, query=query, route=route)

        if not route.should_retrieve:
            return RagResult(enabled=True, query=query, route=route)

        try:
            index = self.ensure_ready()
            if index is None or not index.ready:
                return RagResult(enabled=True, query=query, route=route, error="empty_index")

            expanded_query = self._expand_query(query, route)
            hits = rag_retriever.retrieve(
                index,
                query=expanded_query,
                route=route,
                top_k=settings.rag_top_k,
                min_score=settings.rag_min_score,
            )
            prompt_context = rag_prompt_context_builder.build(
                hits,
                route=route,
                max_chars=settings.rag_max_context_chars,
            )
            return RagResult(
                enabled=True,
                query=query,
                route=route,
                hits=hits,
                prompt_context=prompt_context,
            )
        except Exception as exc:  # noqa: BLE001
            return RagResult(enabled=True, query=query, route=route, error=str(exc))

    def _expand_query(self, query: str, route: SafetyRoute) -> str:
        expansions = [TOPIC_QUERY_EXPANSIONS[topic] for topic in route.topics if topic in TOPIC_QUERY_EXPANSIONS]
        if not expansions:
            return query
        return f"{query}\n" + "\n".join(expansions)

    def _load_or_build_processed_chunks(self, *, force_rebuild: bool = False):
        processed_dir = Path(settings.rag_processed_dir).expanduser()
        chunks = [] if force_rebuild else rag_loader.load_processed_chunks(processed_dir)
        if chunks:
            return chunks
        _, chunks = rag_loader.write_processed(settings.rag_kb_dir, processed_dir)
        return chunks


rag_service = RagService()
