from fastapi import FastAPI
import logging
from pathlib import Path

from routes.cache_identity import router as cache_identity_router
from routes.extract import router as extract_router
from routes.health import router as health_router
from routes.identity import router as identity_router
from services.facial_emotion_runtime import facial_emotion_runtime
from services.qwen_vl_runtime import qwen_vl_runtime
from config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="A22 Vision Service", version="0.1.0")
app.include_router(health_router)
app.include_router(extract_router)
app.include_router(identity_router)
app.include_router(cache_identity_router)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info(
        "vision_storage_paths face_db_dir=%s face_db_path=%s",
        settings.face_db_dir,
        str(Path(settings.face_db_dir) / "faces.json"),
    )
    qwen_vl_runtime.warmup()
    facial_emotion_runtime.warmup()
