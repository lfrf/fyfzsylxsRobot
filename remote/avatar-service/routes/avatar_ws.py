from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from config import settings
from services.avatar_event_bus import avatar_event_bus

router = APIRouter()


@router.websocket("/ws/avatar")
async def avatar_ws(websocket: WebSocket) -> None:
    await avatar_event_bus.connect(websocket)
    await websocket.send_json(
        {
            "event": "connected",
            "websocket_endpoint": settings.websocket_endpoint,
            "transport_mode": settings.transport_mode,
            "contract_version": "a2f-ab-v1",
        }
    )
    try:
        while True:
            message = await websocket.receive_json()
            action = str(message.get("action", "")).strip().lower()
            if action in {"subscribe", "bind"}:
                session_id = message.get("session_id")
                stream_id = message.get("stream_id")
                await avatar_event_bus.set_subscription(
                    websocket,
                    session_id=session_id,
                    stream_id=stream_id,
                )
                await websocket.send_json(
                    {
                        "event": "subscribed",
                        "session_id": session_id,
                        "stream_id": stream_id,
                    }
                )
                continue

            if action == "ping":
                await websocket.send_json({"event": "pong"})
                continue

            await websocket.send_json(
                {
                    "event": "error",
                    "error_code": "BAD_ACTION",
                    "error_message": "Supported actions: subscribe, bind, ping.",
                }
            )
    except WebSocketDisconnect:
        await avatar_event_bus.disconnect(websocket)
    except Exception:
        await avatar_event_bus.disconnect(websocket)
