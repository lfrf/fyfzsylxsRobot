from shared import logging_utils


def _reset_logging_utils() -> None:
    logging_utils._CONFIGURED = False
    logging_utils._LOG_SESSION_ID = None
    logging_utils._LOG_FILE_PATH = None
    logging_utils._LOG_CONTEXT.set({})


def test_log_event_does_not_print_full_audio_base64(monkeypatch, capsys) -> None:
    secret_audio = "UklGRiQAAABXQVZFZm10IBAAAAABAAEA"
    monkeypatch.setenv("ROBOT_LOG_JSON", "true")
    monkeypatch.setenv("ROBOT_LOG_LEVEL", "INFO")
    _reset_logging_utils()

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


def test_log_event_writes_to_session_log_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ROBOT_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("ROBOT_LOG_SESSION_ID", "test-session-001")
    monkeypatch.setenv("ROBOT_LOG_LEVEL", "INFO")
    monkeypatch.setenv("ROBOT_LOG_JSON", "true")
    _reset_logging_utils()

    logging_utils.log_event("diagnostic_event", mode="care")

    log_file = tmp_path / "test-session-001" / "robotmatch.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "diagnostic_event" in content
    assert "test-session-001" in content


def test_start_log_session_generates_china_timezone_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ROBOT_LOG_DIR", str(tmp_path))
    _reset_logging_utils()

    session_id = logging_utils.start_log_session()
    logging_utils.log_event("session_started")

    assert session_id.startswith("cn-")
    assert (tmp_path / session_id / "robotmatch.log").exists()


def test_log_context_writes_matching_remote_session_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ROBOT_LOG_DIR", str(tmp_path))
    monkeypatch.setenv("ROBOT_LOG_SESSION_ID", "remote-process")
    _reset_logging_utils()

    with logging_utils.log_context(log_session_id="cn-20260501-120000-pi123456"):
        logging_utils.log_event("remote_orchestrator_event", mode="care")

    session_log = tmp_path / "cn-20260501-120000-pi123456" / "robotmatch.log"
    assert session_log.exists()
    assert "remote_orchestrator_event" in session_log.read_text(encoding="utf-8")


def test_prompt_log_sanitizes_audio_base64(monkeypatch, capsys) -> None:
    secret_audio = "UklGRiQAAABXQVZFZm10IBAAAAABAAEA"
    monkeypatch.setenv("ROBOT_LOG_JSON", "true")
    monkeypatch.setenv("ROBOT_LOG_LEVEL", "INFO")
    _reset_logging_utils()

    logging_utils.log_event(
        "llm_prompt_built",
        audio_base64=secret_audio,
        prompt_chars=1200,
    )

    output = capsys.readouterr().out
    assert secret_audio not in output
    assert "audio_base64_len" in output
