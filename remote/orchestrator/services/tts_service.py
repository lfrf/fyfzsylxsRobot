from urllib.parse import quote

from contracts.schemas import TTSResult


class RobotTTSService:
    def synthesize(self, *, text: str, session_id: str, turn_id: str) -> TTSResult:
        if not text.strip():
            return TTSResult(type="none", audio_url=None, format="wav")

        safe_session = quote(session_id, safe="")
        safe_turn = quote(turn_id, safe="")
        return TTSResult(
            type="audio_url",
            audio_url=f"mock://tts/{safe_session}/{safe_turn}.wav",
            format="wav",
        )


robot_tts_service = RobotTTSService()

__all__ = ["RobotTTSService", "robot_tts_service"]
