import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_ROOT = PROJECT_ROOT / "remote" / "orchestrator"
SHARED_ROOT = PROJECT_ROOT / "shared"

for path in (PROJECT_ROOT, ORCHESTRATOR_ROOT, SHARED_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
