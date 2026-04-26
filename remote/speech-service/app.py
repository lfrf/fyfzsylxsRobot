from fastapi import FastAPI

from routes.health import router as health_router
from routes.transcribe import router as transcribe_router
from services.asr_runtime import speech_runtime

app = FastAPI(title="A22 Speech Service", version="0.1.0")
app.include_router(health_router)
app.include_router(transcribe_router)


@app.on_event("startup")
async def on_startup() -> None:
    speech_runtime.warmup()
