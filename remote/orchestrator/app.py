from fastapi import FastAPI

from routes.chat import router as chat_router
from routes.chat_ws import router as chat_ws_router
from routes.health import router as health_router
from routes.media import router as media_router
from routes.robot_chat import router as robot_chat_router
from config import settings
from services.observability import orchestrator_observability
from services.rag import rag_service

app = FastAPI(title="A22 Orchestrator", version="0.2.0")
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(chat_ws_router)
app.include_router(media_router)
app.include_router(robot_chat_router)


@app.on_event("startup")
async def on_startup() -> None:
    if settings.rag_enabled:
        rag_service.ensure_ready()
    orchestrator_observability.log_run_start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    orchestrator_observability.log_run_stop()
