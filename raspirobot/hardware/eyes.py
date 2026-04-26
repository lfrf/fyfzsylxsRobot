from dataclasses import dataclass
from typing import Protocol


class EyesDriver(Protocol):
    def set_expression(self, expression: str) -> None:
        ...


@dataclass
class MockEyesDriver:
    last_expression: str = "neutral"

    def set_expression(self, expression: str) -> None:
        self.last_expression = expression or "neutral"

