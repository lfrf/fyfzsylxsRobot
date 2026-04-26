from pathlib import Path
import sys


ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.append(str(ORCHESTRATOR_ROOT))

from config import settings  # noqa: E402
from services.rag.loader import rag_loader  # noqa: E402


def main() -> None:
    documents, chunks = rag_loader.write_processed(settings.rag_kb_dir, settings.rag_processed_dir)
    print(f"RAG chunks built: {len(documents)} documents, {len(chunks)} chunks")
    print(f"processed_dir={settings.rag_processed_dir}")
    if rag_loader.invalid_records:
        print(f"invalid_records={len(rag_loader.invalid_records)}")


if __name__ == "__main__":
    main()
