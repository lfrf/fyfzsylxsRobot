from dataclasses import dataclass
from typing import Protocol


class WakeWordProvider(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def poll(self) -> bool:
        ...


@dataclass
class MockWakeWordProvider:
    triggered: bool = False
    running: bool = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def trigger(self) -> None:
        self.triggered = True

    def poll(self) -> bool:
        if not self.running:
            return False
        was_triggered = self.triggered
        self.triggered = False
        return was_triggered

