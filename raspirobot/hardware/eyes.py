from dataclasses import dataclass
from typing import Protocol

from shared.logging_utils import log_event


class EyesDriver(Protocol):
    def set_expression(self, expression: str) -> None:
        ...


@dataclass
class MockEyesDriver:
    last_expression: str = "neutral"

    def set_expression(self, expression: str) -> None:
        self.last_expression = expression or "neutral"
        log_event(
            "hardware_eyes_expression_set",
            provider="mock",
            expression=self.last_expression,
        )
