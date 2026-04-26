from fastapi import FastAPI

from routes.chat import router as chat_router
from routes.health import router as health_router
from services.observability import edge_observability

app = FastAPI(title="A22 Edge Backend", version="0.2.0")
app.include_router(health_router)
app.include_router(chat_router)


@app.on_event("startup")
async def on_startup() -> None:
    edge_observability.log_run_start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    edge_observability.log_run_stop()
