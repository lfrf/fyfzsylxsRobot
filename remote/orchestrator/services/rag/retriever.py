from services.rag.contracts import RagHit, SafetyRoute
from services.rag.index import RagIndex


class RagRetriever:
    def retrieve(
        self,
        index: RagIndex,
        *,
        query: str,
        route: SafetyRoute,
        top_k: int,
        min_score: float,
    ) -> list[RagHit]:
        return index.search(
            query,
            top_k=top_k,
            min_score=min_score,
            topics=route.topics,
            source_levels=route.source_levels,
            risk_level=route.risk_level,
        )


rag_retriever = RagRetriever()
