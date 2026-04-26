from fastapi import FastAPI

from routes.avatar_ws import router as avatar_ws_router
from routes.generate import router as generate_router
from routes.health import router as health_router
from routes.media import router as media_router
from services.tts_runtime import tts_runtime

app = FastAPI(title="A22 Avatar Service", version="0.1.0")
app.include_router(health_router)
app.include_router(generate_router)
app.include_router(media_router)
app.include_router(avatar_ws_router)


@app.on_event("startup")
async def on_startup() -> None:
    tts_runtime.warmup()
