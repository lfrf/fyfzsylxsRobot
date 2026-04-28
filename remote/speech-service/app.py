from fastapi import FastAPI

from routes.asr import router as asr_router
from routes.health import router as health_router
from routes.tts import router as tts_router
from routes.transcribe import router as transcribe_router
from services.asr_runtime import speech_runtime
from services.tts_service import tts_service

app = FastAPI(title="A22 Speech Service", version="0.1.0")
app.include_router(health_router)
app.include_router(asr_router)
app.include_router(transcribe_router)
app.include_router(tts_router)


@app.on_event("startup")
async def on_startup() -> None:
    speech_runtime.warmup()
    tts_service.warmup()
