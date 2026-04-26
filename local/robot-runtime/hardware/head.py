from dataclasses import dataclass


@dataclass
class HeadController:
    mode: str = "mock"
    pan_channel: int = 0
    tilt_channel: int = 1
    min_degree: int = 70
    max_degree: int = 110
    last_pan_degree: int = 90
    last_tilt_degree: int = 90

    def _clamp(self, value: int) -> int:
        return max(self.min_degree, min(self.max_degree, value))

    def set_pose(self, pan_degree: int, tilt_degree: int) -> None:
        self.last_pan_degree = self._clamp(pan_degree)
        self.last_tilt_degree = self._clamp(tilt_degree)
        if self.mode == "mock":
            return
        # Hardware mode placeholder:
        # - convert degree to PWM pulse
        # - send to PCA9685 channels

    def center(self) -> None:
        center = (self.min_degree + self.max_degree) // 2
        self.set_pose(center, center)
