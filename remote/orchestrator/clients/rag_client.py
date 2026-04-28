from __future__ import annotations


class RAGClient:
    def retrieve_context(self, *, namespace: str, query: str) -> str | None:
        return None


rag_client = RAGClient()

__all__ = ["RAGClient", "rag_client"]
