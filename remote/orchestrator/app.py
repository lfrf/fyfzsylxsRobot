from fastapi import FastAPI

from routes.health import router as health_router
from routes.robot_media import router as robot_media_router
from routes.robot_chat import router as robot_chat_router
from config import settings
from services.observability import orchestrator_observability
from services.rag import rag_service

app = FastAPI(title="RobotMatch Orchestrator", version="0.3.0")
app.include_router(health_router)
app.include_router(robot_chat_router)
app.include_router(robot_media_router)


@app.on_event("startup")
async def on_startup() -> None:
    if settings.rag_enabled:
        rag_service.ensure_ready()
    orchestrator_observability.log_run_start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    orchestrator_observability.log_run_stop()
