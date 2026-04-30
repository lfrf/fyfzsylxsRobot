from raspirobot.actions import DefaultRobotActionDispatcher
from raspirobot.audio import MockAudioPlayer, MockAudioRecorder, MockWakeWordProvider
from raspirobot.hardware import MockEyesDriver, MockHeadDriver
from raspirobot.remote_client import MockRemoteClient
from raspirobot.state_machine import RobotEvent, RobotRuntimeState, RobotStateMachine
from raspirobot.vision import MockFaceTracker, MockVisionContextProvider
from shared.schemas import RobotAction, RobotChatRequest, RobotState, TTSResult


def test_robot_skeleton_smoke() -> None:
    state_machine = RobotStateMachine()
    assert state_machine.transition(RobotEvent.WAKE_WORD_DETECTED) == RobotRuntimeState.WAKE_DETECTED
    assert state_machine.transition(RobotEvent.WAKE_ACK_DONE) == RobotRuntimeState.LISTENING

    wake = MockWakeWordProvider()
    wake.start()
    wake.trigger()
    assert wake.poll() is True

    recorder = MockAudioRecorder(text_hint="你好")
    robot_input = recorder.record_turn()
    vision = MockVisionContextProvider(face_tracker=MockFaceTracker())
    request = RobotChatRequest(
        session_id="demo-session-001",
        turn_id="turn-0001",
        mode="care",
        input=robot_input,
        vision_context=vision.get_context(),
        robot_state=RobotState(state=state_machine.state.value),
    )

    response = MockRemoteClient().chat_turn(request)
    assert response.success is True
    assert response.mode.mode_id == "care"

    eyes = MockEyesDriver()
    head = MockHeadDriver()
    audio = MockAudioPlayer()
    dispatcher = DefaultRobotActionDispatcher(eyes=eyes, head=head, audio=audio)
    dispatcher.dispatch(
        RobotAction(expression="comfort", motion="slow_nod", head_target={"pan": 90, "tilt": 94}),
        TTSResult(audio_url="mock://tts.wav"),
    )

    assert eyes.last_expression == "comfort"
    assert head.last_motion == "slow_nod"
    assert audio.played_urls == ["mock://tts.wav"]
