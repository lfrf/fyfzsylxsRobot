from pathlib import Path
import sys


ORCHESTRATOR_ROOT = Path(__file__).resolve().parents[1]
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.append(str(ORCHESTRATOR_ROOT))

from services.rag.service import rag_service  # noqa: E402


def main() -> None:
    index = rag_service.rebuild_index()
    print(f"RAG index built from processed chunks: {len(index.chunks)} chunks")


if __name__ == "__main__":
    main()
