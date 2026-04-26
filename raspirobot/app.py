from .config import load_settings
from .state_machine import RobotStateMachine

try:
    from fastapi import FastAPI
except ImportError:  # pragma: no cover
    FastAPI = None


settings = load_settings()
state_machine = RobotStateMachine(mode_id=settings.default_mode)


def create_app():
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed.")

    app = FastAPI(title="RobotMatch raspirobot", version="0.1.0")

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "hardware_mode": "mock",
            "remote_base_url": settings.remote_base_url,
            "state": state_machine.state.value,
            "mode": state_machine.mode_id,
        }

    return app


app = create_app() if FastAPI is not None else None
