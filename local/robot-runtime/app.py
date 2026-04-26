from fastapi import FastAPI, HTTPException

from config import load_settings
from models import (
    ChatForwardPayload,
    ChatTextRequest,
    EyeExpressionRequest,
    HeadPoseRequest,
    HealthResponse,
    RuntimeStateResponse,
)
from runtime import RobotRuntime

settings = load_settings()
runtime = RobotRuntime.from_settings(settings)

app = FastAPI(title="A22 Robot Runtime", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        edge_backend_base=settings.edge_backend_base,
        eyes_mode=settings.eyes_mode,
        servo_mode=settings.servo_mode,
        audio_mode=settings.audio_mode,
    )


@app.get("/v1/runtime/state", response_model=RuntimeStateResponse)
async def runtime_state() -> RuntimeStateResponse:
    return RuntimeStateResponse(
        last_expression=runtime.eyes.last_expression,
        last_pan_degree=runtime.head.last_pan_degree,
        last_tilt_degree=runtime.head.last_tilt_degree,
        last_reply_text=runtime.last_reply_text,
        last_emotion_style=runtime.last_emotion_style,
    )


@app.post("/v1/eyes/expression", response_model=RuntimeStateResponse)
async def set_eye_expression(request: EyeExpressionRequest) -> RuntimeStateResponse:
    runtime.eyes.set_expression(request.expression)
    return await runtime_state()


@app.post("/v1/head/pose", response_model=RuntimeStateResponse)
async def set_head_pose(request: HeadPoseRequest) -> RuntimeStateResponse:
    runtime.head.set_pose(request.pan_degree, request.tilt_degree)
    return await runtime_state()


@app.post("/v1/chat/text")
async def chat_text(request: ChatTextRequest) -> dict:
    payload = ChatForwardPayload(
        session_id=request.session_id,
        turn_id=request.turn_id,
        user_text=request.text,
    )
    try:
        response = await runtime.forward_text_chat(payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to forward chat: {exc}") from exc
    return {
        "status": "ok",
        "reply": response,
        "runtime_state": (await runtime_state()).model_dump(),
    }
