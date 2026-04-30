import sys
from pathlib import Path

from fastapi import APIRouter, Request

SHARED_PATH_CANDIDATES = [
    Path("/shared"),
    Path(__file__).resolve().parents[3] / "shared",
]

for candidate in SHARED_PATH_CANDIDATES:
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.append(str(candidate))

from contracts.schemas import RobotChatRequest, RobotChatResponse  # noqa: E402
from services.robot_chat_service import robot_chat_service  # noqa: E402

router = APIRouter()


@router.post("/v1/robot/chat_turn", response_model=RobotChatResponse)
async def robot_chat_turn(request: RobotChatRequest, http_request: Request) -> RobotChatResponse:
    log_session_id = http_request.headers.get("x-robot-log-session-id")
    if log_session_id and "log_session_id" not in request.request_options:
        request.request_options["log_session_id"] = log_session_id
    return robot_chat_service.handle_chat_turn(request)
