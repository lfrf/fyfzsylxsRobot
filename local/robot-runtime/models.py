from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    edge_backend_base: str
    eyes_mode: str
    servo_mode: str
    audio_mode: str


class ChatTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None
    turn_id: int | None = Field(default=None, ge=1)


class HeadPoseRequest(BaseModel):
    pan_degree: int = Field(..., ge=0, le=180)
    tilt_degree: int = Field(..., ge=0, le=180)


class EyeExpressionRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=64)


class RuntimeStateResponse(BaseModel):
    last_expression: str
    last_pan_degree: int
    last_tilt_degree: int
    last_reply_text: str | None = None
    last_emotion_style: str | None = None


class ChatForwardPayload(BaseModel):
    session_id: str | None = None
    turn_id: int | None = Field(default=None, ge=1)
    user_text: str
    input_type: str = "text"
