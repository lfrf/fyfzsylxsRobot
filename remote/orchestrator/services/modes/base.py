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
    few_shot_filename: str = ""
    output_constraint_filename: str = ""
    switch_commands: tuple[str, ...] = ()

    @property
    def instruction_path(self) -> Path:
        return Path(__file__).resolve().parent / "instructions" / self.instruction_filename

    @property
    def few_shot_path(self) -> Path:
        return Path(__file__).resolve().parent / "few_shots" / self.few_shot_filename

    @property
    def output_constraint_path(self) -> Path:
        return Path(__file__).resolve().parent / "output_constraints" / self.output_constraint_filename

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

    def load_few_shots(self) -> str:
        if not self.few_shot_filename:
            return ""
        path = self.few_shot_path
        if path.exists():
            few_shots = path.read_text(encoding="utf-8").strip()
            log_event(
                "mode_few_shots_loaded",
                mode_id=self.mode_id,
                few_shot_path=str(path),
                few_shot_chars=len(few_shots),
                loaded=True,
            )
            return few_shots
        log_event(
            "mode_few_shots_loaded",
            mode_id=self.mode_id,
            few_shot_path=str(path),
            few_shot_chars=0,
            loaded=False,
            reason="few_shot_file_missing",
        )
        return ""

    def load_output_constraints(self) -> str:
        if not self.output_constraint_filename:
            return ""
        path = self.output_constraint_path
        if path.exists():
            output_constraints = path.read_text(encoding="utf-8").strip()
            log_event(
                "mode_output_constraints_loaded",
                mode_id=self.mode_id,
                output_constraint_path=str(path),
                output_constraint_chars=len(output_constraints),
                loaded=True,
            )
            return output_constraints
        log_event(
            "mode_output_constraints_loaded",
            mode_id=self.mode_id,
            output_constraint_path=str(path),
            output_constraint_chars=0,
            loaded=False,
            reason="output_constraint_file_missing",
        )
        return ""

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
            few_shot_path=str(self.few_shot_path) if self.few_shot_filename else "",
            few_shots=self.load_few_shots(),
            output_constraint_path=str(self.output_constraint_path) if self.output_constraint_filename else "",
            output_constraints=self.load_output_constraints(),
        )
