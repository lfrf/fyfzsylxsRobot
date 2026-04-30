from __future__ import annotations

from services.mode_types import ModePolicy, ModeService

from .accompany_mode import AccompanyModeService
from .care_mode import CareModeService
from .game_mode import GameModeService
from .learning_mode import LearningModeService


DEFAULT_MODE_ID = "care"

_SERVICES: tuple[ModeService, ...] = (
    CareModeService(),
    AccompanyModeService(),
    LearningModeService(),
    GameModeService(),
)

MODE_SERVICES: dict[str, ModeService] = {service.mode_id: service for service in _SERVICES}
MODE_POLICIES: dict[str, ModePolicy] = {mode_id: service.get_policy() for mode_id, service in MODE_SERVICES.items()}
MODE_COMMANDS: dict[str, tuple[str, ...]] = {mode_id: service.switch_commands for mode_id, service in MODE_SERVICES.items()}

_MODE_ALIASES = {
    "care": "care",
    "elderly": "care",
    "accompany": "accompany",
    "normal": "accompany",
    "learning": "learning",
    "student": "learning",
    "game": "game",
    "child": "game",
}


def normalize_mode(mode_id: str | None) -> str:
    key = (mode_id or "").strip().lower()
    return _MODE_ALIASES.get(key, DEFAULT_MODE_ID)


def get_mode_service(mode_id: str | None) -> ModeService:
    return MODE_SERVICES[normalize_mode(mode_id)]


def get_mode_policy(mode_id: str | None) -> ModePolicy:
    return MODE_POLICIES[normalize_mode(mode_id)]
