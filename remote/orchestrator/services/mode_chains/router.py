from __future__ import annotations

from services.mode_policy import normalize_mode

from .accompany_chain import AccompanyModeChain
from .base import BaseModeChain
from .care_chain import CareModeChain
from .game_chain import GameModeChain
from .learning_chain import LearningModeChain


class ModeChainRouter:
    def __init__(self) -> None:
        self._chains: dict[str, BaseModeChain] = {
            "care": CareModeChain(),
            "accompany": AccompanyModeChain(),
            "learning": LearningModeChain(),
            "game": GameModeChain(),
        }

    def get_chain(self, mode_id: str | None) -> BaseModeChain:
        return self._chains[normalize_mode(mode_id)]


mode_chain_router = ModeChainRouter()


def get_chain(mode_id: str | None) -> BaseModeChain:
    return mode_chain_router.get_chain(mode_id)


__all__ = ["ModeChainRouter", "get_chain", "mode_chain_router"]
