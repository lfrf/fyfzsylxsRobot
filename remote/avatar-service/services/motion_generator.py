class MotionGenerator:
    def generate(self, *, motion: str, duration_ms: int) -> list[dict]:
        return [
            {
                "start_ms": 0,
                "end_ms": duration_ms,
                "motion": motion,
                "intensity": 0.6,
            }
        ]


motion_generator = MotionGenerator()
