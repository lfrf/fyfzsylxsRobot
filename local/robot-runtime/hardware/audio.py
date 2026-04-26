from dataclasses import dataclass


@dataclass
class AudioPlayer:
    mode: str = "mock"

    def play_text(self, text: str) -> None:
        if self.mode == "mock":
            return
        # Hardware mode placeholder:
        # - call local TTS endpoint or engine
        # - stream PCM to default output device
