from __future__ import annotations

import argparse

from raspirobot.actions import DefaultRobotActionDispatcher
from raspirobot.audio import LocalCommandAudioOutputProvider, MockAudioOutputProvider
from raspirobot.config import load_settings
from raspirobot.hardware import MockEyesDriver, MockHeadDriver
from raspirobot.remote import RemoteClient, RobotPayloadBuilder
from raspirobot.session import SessionManager, TurnLogger
from raspirobot.core import TurnManager
from raspirobot.vision import MockVisionContextProvider


def main() -> None:
    parser = argparse.ArgumentParser(description="Send an existing wav through the SSH tunnel robot endpoint.")
    parser.add_argument("--wav", required=True, help="Path to an existing wav file.")
    parser.add_argument("--play", action="store_true", help="Download and play returned tts.audio_url if available.")
    args = parser.parse_args()

    settings = load_settings()
    remote = RemoteClient()
    audio = (
        LocalCommandAudioOutputProvider(
            command=settings.audio_playback_command,
            playback_device=settings.audio_playback_device,
            download_dir=f"{settings.audio_work_dir}/playback",
        )
        if args.play
        else MockAudioOutputProvider()
    )
    session = SessionManager(session_id=settings.session_id, mode_id=settings.default_mode)
    dispatcher = DefaultRobotActionDispatcher(
        eyes=MockEyesDriver(),
        head=MockHeadDriver(),
        audio=None,
        remote_base_url=remote.base_url,
    )
    manager = TurnManager(
        payload_builder=RobotPayloadBuilder(
            session_id=settings.session_id,
            mode_id=settings.default_mode,
            vision_context_provider=MockVisionContextProvider(),
        ),
        remote_client=remote,
        action_dispatcher=dispatcher,
        audio_output=audio,
        session=session,
        logger=TurnLogger(),
    )

    result = manager.handle_utterance(args.wav)
    print(f"turn_id={result.response.turn_id}")
    print(f"asr_text={result.response.asr_text}")
    print(f"reply_text={result.response.reply_text}")
    print(f"tts_audio_url={result.response.tts.audio_url}")
    print(f"playback={result.playback}")


if __name__ == "__main__":
    main()
