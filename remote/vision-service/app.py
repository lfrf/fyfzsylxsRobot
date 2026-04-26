from fastapi import FastAPI

from routes.extract import router as extract_router
from routes.health import router as health_router
from services.facial_emotion_runtime import facial_emotion_runtime
from services.qwen_vl_runtime import qwen_vl_runtime

app = FastAPI(title="A22 Vision Service", version="0.1.0")
app.include_router(health_router)
app.include_router(extract_router)


@app.on_event("startup")
async def on_startup() -> None:
    qwen_vl_runtime.warmup()
    facial_emotion_runtime.warmup()
