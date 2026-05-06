from __future__ import annotations

from fastapi import FastAPI

from routes.health import router as health_router
from routes.ingest import router as ingest_router
from routes.query import router as query_router
from services.buffer import video_buffer

app = FastAPI(title="A22 Video Cache Service", version="0.1.0")
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(query_router)


@app.on_event("startup")
async def on_startup() -> None:
    video_buffer.clear()
