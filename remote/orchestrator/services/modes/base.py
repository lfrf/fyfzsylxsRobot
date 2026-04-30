from __future__ import annotations

from pathlib import Path

from logging_utils import log_event
from services.mode_types import ModePolicy


class BaseModeService:
    mode_id: str = ""
    display_name: str = ""
    prompt_policy: str = ""
    rag_namespace: str = ""
    action_style: str = ""
    speech_style: str = ""
    confirmation_text: str = ""
    normal_reply: str = ""
    switch_expression: str = "neutral"
    switch_motion: str = "center"
    instruction_filename: str = ""
    fallback_instruction: str = ""
    switch_commands: tuple[str, ...] = ()

    @property
    def instruction_path(self) -> Path:
        return Path(__file__).resolve().parent / "instructions" / self.instruction_filename

    def load_instruction(self) -> str:
        path = self.instruction_path
        if path.exists():
            instruction = path.read_text(encoding="utf-8").strip()
            log_event(
                "mode_instruction_loaded",
                mode_id=self.mode_id,
                instruction_path=str(path),
                instruction_chars=len(instruction),
                fallback_used=False,
            )
            return instruction
        instruction = self.fallback_instruction.strip()
        log_event(
            "mode_instruction_loaded",
            mode_id=self.mode_id,
            instruction_path=str(path),
            instruction_chars=len(instruction),
            fallback_used=True,
            reason="instruction_file_missing",
        )
        return instruction

    def get_policy(self) -> ModePolicy:
        return ModePolicy(
            mode_id=self.mode_id,
            display_name=self.display_name,
            prompt_policy=self.prompt_policy,
            rag_namespace=self.rag_namespace,
            action_style=self.action_style,
            speech_style=self.speech_style,
            confirmation_text=self.confirmation_text,
            normal_reply=self.normal_reply,
            switch_expression=self.switch_expression,
            switch_motion=self.switch_motion,
            instruction_path=str(self.instruction_path),
            system_instruction=self.load_instruction(),
        )
