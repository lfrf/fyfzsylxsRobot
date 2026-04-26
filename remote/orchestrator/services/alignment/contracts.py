from dataclasses import dataclass


@dataclass
class AlignedTurn:
    canonical_user_text: str
    llm_user_text: str
    alignment_mode: str
    alignment_summary: str | None = None
    speech_context: str | None = None
    vision_context: str | None = None
