VISEME_LABELS = ["a", "e", "i", "o", "u", "m"]
PAUSE_LABEL = "sil"
MAX_VISEME_SEGMENTS = 120
PAUSE_CHARS = set(" \t\r\n，。！？；：、,.!?;:…—-()[]{}<>\"'“”‘’")

LATIN_TO_VISEME = {
    "a": "a",
    "e": "e",
    "i": "i",
    "o": "o",
    "u": "u",
    "v": "u",
    "w": "u",
    "y": "i",
    "b": "m",
    "m": "m",
    "p": "m",
    "f": "m",
}

VISEME_WEIGHT = {
    "a": 0.74,
    "e": 0.64,
    "i": 0.60,
    "o": 0.71,
    "u": 0.67,
    "m": 0.52,
    PAUSE_LABEL: 0.05,
}


def _compress_units(units: list[str], max_units: int) -> list[str]:
    if len(units) <= max_units:
        return units
    # Uniform down-sampling keeps temporal distribution stable for long texts.
    out: list[str] = []
    last_idx = -1
    for i in range(max_units):
        idx = round(i * (len(units) - 1) / (max_units - 1))
        if idx == last_idx:
            continue
        out.append(units[idx])
        last_idx = idx
    return out


def _char_to_viseme(ch: str, voiced_index: int) -> str:
    low = ch.lower()
    if low in LATIN_TO_VISEME:
        return LATIN_TO_VISEME[low]
    if low.isdigit():
        return VISEME_LABELS[int(low) % len(VISEME_LABELS)]
    return VISEME_LABELS[voiced_index % len(VISEME_LABELS)]


class VisemeGenerator:
    def _build_units(self, text: str) -> list[str]:
        text = (text or "").strip()
        if not text:
            return [PAUSE_LABEL]

        units: list[str] = []
        voiced_index = 0

        for ch in text:
            if ch in PAUSE_CHARS:
                if not units or units[-1] != PAUSE_LABEL:
                    units.append(PAUSE_LABEL)
                continue

            label = _char_to_viseme(ch, voiced_index)
            units.append(label)
            voiced_index += 1

        if not units:
            return [PAUSE_LABEL]

        return _compress_units(units, MAX_VISEME_SEGMENTS)

    def generate(self, *, text: str, duration_ms: int) -> list[dict]:
        safe_duration = max(300, int(duration_ms or 0))
        units = self._build_units(text)

        weights = [0.75 if unit != PAUSE_LABEL else 0.40 for unit in units]
        total_weight = float(sum(weights)) if weights else 1.0

        visemes: list[dict] = []
        cursor = 0
        cumulative = 0.0

        for index, label in enumerate(units):
            cumulative += weights[index]
            if index == len(units) - 1:
                next_cursor = safe_duration
            else:
                next_cursor = int(round((cumulative / total_weight) * safe_duration))
                if next_cursor <= cursor:
                    next_cursor = min(safe_duration, cursor + 1)

            visemes.append(
                {
                    "start_ms": cursor,
                    "end_ms": next_cursor,
                    "label": label,
                    "weight": VISEME_WEIGHT.get(label, 0.55),
                }
            )
            cursor = next_cursor

        return visemes


viseme_generator = VisemeGenerator()
