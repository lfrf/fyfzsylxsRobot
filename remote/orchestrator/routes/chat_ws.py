from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from models import ChatRequest
from routes.chat import process_chat_request

router = APIRouter()


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    while True:
        try:
            payload = await websocket.receive_json()
        except WebSocketDisconnect:
            return
        except Exception:  # noqa: BLE001
            await websocket.send_json(
                {
                    "detail": "Invalid websocket JSON payload.",
                    "status_code": 400,
                }
            )
            continue

        try:
            if hasattr(ChatRequest, "model_validate"):
                request = ChatRequest.model_validate(payload)
            else:
                request = ChatRequest(**payload)
        except ValidationError as exc:
            await websocket.send_json(
                {
                    "detail": "Invalid chat request schema.",
                    "status_code": 422,
                    "errors": exc.errors(),
                }
            )
            continue

        try:
            response = await process_chat_request(request)
            response_payload = response.model_dump() if hasattr(response, "model_dump") else response.dict()
            await websocket.send_json(response_payload)
        except Exception as exc:  # noqa: BLE001
            status_code = getattr(exc, "status_code", 500)
            detail = getattr(exc, "detail", str(exc) or "Remote orchestrator websocket handling failed.")
            await websocket.send_json(
                {
                    "detail": detail,
                    "status_code": status_code,
                }
            )
