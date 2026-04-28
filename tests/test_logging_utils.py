from shared import logging_utils


def test_log_event_does_not_print_full_audio_base64(monkeypatch, capsys) -> None:
    secret_audio = "UklGRiQAAABXQVZFZm10IBAAAAABAAEA"
    monkeypatch.setenv("ROBOT_LOG_JSON", "true")
    monkeypatch.setenv("ROBOT_LOG_LEVEL", "INFO")
    logging_utils._CONFIGURED = False

    logging_utils.log_event(
        "payload_built",
        session_id="session-log",
        audio_base64=secret_audio,
        sample_rate=16000,
    )

    output = capsys.readouterr().out
    assert secret_audio not in output
    assert "audio_base64_len" in output
    assert str(len(secret_audio)) in output
