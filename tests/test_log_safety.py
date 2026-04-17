import io
import json

from local_ai_agent.config import Settings
from local_ai_agent.logging_utils import InteractionLogger
from local_ai_agent.router.runtime_services import JsonlRouterEventSink


def test_redact_secrets_scrubs_common_keys_recursively():
    from local_ai_agent.log_safety import redact_secrets

    payload = {
        "api_key": "SECRET",
        "nested": {
            "authorization": "Bearer SECRET2",
            "items": [{"token": "SECRET3"}],
        },
        "access_token": "SECRET4",
        "refresh_token": "SECRET5",
        "bearer": "SECRET6",
    }

    redacted = redact_secrets(payload)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["authorization"] == "[REDACTED]"
    assert redacted["nested"]["items"][0]["token"] == "[REDACTED]"
    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["refresh_token"] == "[REDACTED]"
    assert redacted["bearer"] == "[REDACTED]"


def test_interaction_logger_redacts_payload_and_rotates_files(tmp_path):
    logger = InteractionLogger(
        logs_dir=tmp_path / "interaction",
        session_id="session-1",
        max_bytes=120,
        max_backups=2,
    )

    for index in range(6):
        logger.log_interaction(
            {
                "request": {
                    "api_key": f"SECRET-{index}",
                    "nested": {"token": f"TOKEN-{index}"},
                },
                "response": {"authorization": f"Bearer SECRET-{index}"},
            }
        )

    log_dir = tmp_path / "interaction"
    current_payload = json.loads((log_dir / "session-1.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert current_payload["request"]["api_key"] == "[REDACTED]"
    assert current_payload["request"]["nested"]["token"] == "[REDACTED]"
    assert current_payload["response"]["authorization"] == "[REDACTED]"
    assert (log_dir / "session-1.jsonl.1").exists()
    assert (log_dir / "session-1.jsonl.2").exists()
    assert not (log_dir / "session-1.jsonl.3").exists()


def test_jsonl_router_event_sink_redacts_payload_and_rotates_files(tmp_path):
    sink = JsonlRouterEventSink(
        log_path=tmp_path / "router" / "session-1.jsonl",
        max_bytes=120,
        max_backups=2,
    )

    for index in range(6):
        sink.emit(
            {
                "event_name": "router.test",
                "api_key": f"SECRET-{index}",
                "diagnostics": {
                    "authorization": f"Bearer SECRET-{index}",
                    "items": [{"token": f"TOKEN-{index}"}],
                },
            }
        )

    log_dir = tmp_path / "router"
    current_payload = json.loads((log_dir / "session-1.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert current_payload["api_key"] == "[REDACTED]"
    assert current_payload["diagnostics"]["authorization"] == "[REDACTED]"
    assert current_payload["diagnostics"]["items"][0]["token"] == "[REDACTED]"
    assert (log_dir / "session-1.jsonl.1").exists()
    assert (log_dir / "session-1.jsonl.2").exists()
    assert not (log_dir / "session-1.jsonl.3").exists()


def test_runtime_wires_log_limits_into_both_sinks(tmp_path, monkeypatch):
    from local_ai_agent.runtime import build_runtime

    monkeypatch.setattr("local_ai_agent.runtime.build_multimodal_input_processor", lambda settings: object())

    settings = Settings(
        provider="stub",
        api_key="test-key",
        session_id="session-1",
        logs_dir=tmp_path / "logs",
        logs_max_bytes=120,
        logs_max_backups=2,
    )

    runtime = build_runtime(settings, stdin=io.StringIO(""), stdout=io.StringIO())

    assert runtime.runner.agent.logger.max_bytes == 120
    assert runtime.runner.agent.logger.max_backups == 2
    assert runtime.router_runtime.event_sink.max_bytes == 120
    assert runtime.router_runtime.event_sink.max_backups == 2
