from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from contracts.schemas import ModeInfo


@dataclass(frozen=True)
class ModePolicy:
    mode_id: str
    display_name: str
    prompt_policy: str
    rag_namespace: str
    action_style: str
    speech_style: str
    confirmation_text: str
    normal_reply: str
    switch_expression: str
    switch_motion: str
    instruction_path: str
    system_instruction: str

    def to_mode_info(self) -> ModeInfo:
        return ModeInfo(
            mode_id=self.mode_id,
            display_name=self.display_name,
            prompt_policy=self.prompt_policy,
            rag_namespace=self.rag_namespace,
            action_style=self.action_style,
        )


class ModeService(Protocol):
    mode_id: str
    display_name: str
    switch_commands: tuple[str, ...]

    def get_policy(self) -> ModePolicy:
        ...

    def load_instruction(self) -> str:
        ...
