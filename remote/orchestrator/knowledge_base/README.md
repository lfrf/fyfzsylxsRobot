# A22 Orchestrator Knowledge Base

This directory contains the Phase 1 in-process RAG knowledge base for the
remote orchestrator.

Layout:

- `raw/`: curated Markdown knowledge files with YAML-style front matter.
- `processed/`: normalized chunk artifacts generated from `raw/`.
- `indexes/`: generated retrieval indexes. These files can be rebuilt.

Current flow:

```text
raw/*.md
  -> scripts/build_rag_chunks.py
  -> processed/chunks.jsonl + processed/chunk_stats.json
  -> scripts/build_rag_index.py
  -> indexes/chunks.jsonl + indexes/index_meta.json
```

The current implementation is intentionally self-contained: it builds a local
lexical retrieval index from processed chunks. Future dense embedding / FAISS
support can reuse the same raw document format and processed chunk contract.
