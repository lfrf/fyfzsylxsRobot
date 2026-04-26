class ExpressionGenerator:
    def generate(self, *, expression: str, duration_ms: int) -> list[dict]:
        return [
            {
                "start_ms": 0,
                "end_ms": duration_ms,
                "expression": expression,
                "intensity": 0.72,
            }
        ]


expression_generator = ExpressionGenerator()
