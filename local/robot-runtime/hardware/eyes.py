from dataclasses import dataclass


@dataclass
class EyesController:
    mode: str = "mock"
    last_expression: str = "neutral"

    def set_expression(self, expression: str) -> None:
        cleaned = expression.strip().lower() or "neutral"
        self.last_expression = cleaned
        if self.mode == "mock":
            return
        # Hardware mode placeholder:
        # - write I2C bytes to dual OLED modules
        # - or dispatch to TCA9548A channels for left/right display

