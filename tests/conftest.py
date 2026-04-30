import os
import sys
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR_ROOT = PROJECT_ROOT / "remote" / "orchestrator"
SHARED_ROOT = PROJECT_ROOT / "shared"

os.environ.setdefault("ROBOT_LOG_DIR", str(Path(tempfile.gettempdir()) / "robotmatch_pytest_logs"))

for path in (PROJECT_ROOT, ORCHESTRATOR_ROOT, SHARED_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def _isolate_robot_logs(monkeypatch, tmp_path):
    monkeypatch.setenv("ROBOT_LOG_DIR", str(tmp_path / "logs"))
    for module_name in ("logging_utils", "shared.logging_utils"):
        module = sys.modules.get(module_name)
        if module is not None:
            module._CONFIGURED = False
            module._LOG_SESSION_ID = None
            module._LOG_FILE_PATH = None
