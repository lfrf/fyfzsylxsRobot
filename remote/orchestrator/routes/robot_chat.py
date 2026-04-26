import sys
from pathlib import Path

from fastapi import APIRouter

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
async def robot_chat_turn(request: RobotChatRequest) -> RobotChatResponse:
    return robot_chat_service.handle_chat_turn(request)
