import io
import logging

import pytest

from local_ai_agent.config import Settings
from local_ai_agent.memory import ConversationMemory, PersistentConversationMemory


def test_runtime_builds_in_memory_store_by_default():
    from local_ai_agent.runtime import build_memory_store

    settings = Settings(provider="stub")

    memory = build_memory_store(settings)

    assert isinstance(memory, ConversationMemory)
    assert not isinstance(memory, PersistentConversationMemory)


def test_runtime_builds_persistent_memory_store_when_enabled(tmp_path):
    from local_ai_agent.runtime import build_memory_store

    settings = Settings(
        provider="stub",
        persistent_memory_enabled=True,
        memory_dir=tmp_path,
        session_id="session-123",
        system_prompt="Stay helpful.",
        max_memory_messages=5,
    )

    memory = build_memory_store(settings)

    assert isinstance(memory, PersistentConversationMemory)
    assert memory.storage_path == tmp_path / "session-123.jsonl"


def test_runtime_builds_app_runtime_without_cli_memory_selection(monkeypatch):
    from local_ai_agent.runtime import AppRuntime, build_runtime

    calls = {"memory": 0}

    def fake_build_memory_store(settings):
        calls["memory"] += 1
        return ConversationMemory(max_messages=settings.max_memory_messages, system_prompt=settings.system_prompt)

    monkeypatch.setattr("local_ai_agent.runtime.build_multimodal_input_processor", lambda settings: object())
    monkeypatch.setattr("local_ai_agent.runtime.build_memory_store", fake_build_memory_store)
    monkeypatch.setattr("local_ai_agent.runtime.build_provider", lambda settings: object())

    settings = Settings(api_key="test-key")
    runtime = build_runtime(settings, stdin=io.StringIO(""), stdout=io.StringIO())

    assert isinstance(runtime, AppRuntime)
    assert calls["memory"] == 1


def test_runtime_builds_multimodal_processor_with_project_local_binary_and_logs_path(tmp_path, caplog):
    from local_ai_agent.runtime import build_multimodal_input_processor

    binary_path = tmp_path / "bin" / "tesseract" / "tesseract.exe"
    binary_path.parent.mkdir(parents=True)
    binary_path.write_text("fake-binary", encoding="utf-8")

    settings = Settings(provider="stub", tesseract_command="bin/tesseract/tesseract.exe")

    with caplog.at_level(logging.INFO):
        processor = build_multimodal_input_processor(settings, project_root=tmp_path)

    assert processor.ocr_extractor.command == str(binary_path.resolve())
    assert str(binary_path.resolve()) in caplog.text


def test_settings_from_env_reads_repo_local_dotenv_for_tesseract_command(tmp_path, monkeypatch):
    from local_ai_agent import config as config_module

    (tmp_path / ".env").write_text("LOCAL_AI_AGENT_TESSERACT_COMMAND=bin/tesseract/tesseract.exe\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("LOCAL_AI_AGENT_TESSERACT_COMMAND", raising=False)
    monkeypatch.setenv("LOCAL_AI_AGENT_PROVIDER", "stub")

    settings = config_module.Settings.from_env()

    assert settings.tesseract_command == "bin/tesseract/tesseract.exe"


def test_runtime_fails_fast_when_configured_binary_is_not_project_local(tmp_path):
    from local_ai_agent.ocr_extractors import OCRExtractionError
    from local_ai_agent.runtime import build_multimodal_input_processor

    outside_binary = tmp_path.parent / "external-tesseract.exe"
    outside_binary.write_text("fake-binary", encoding="utf-8")
    settings = Settings(provider="stub", tesseract_command=str(outside_binary))

    with pytest.raises(OCRExtractionError, match="inside the project root"):
        build_multimodal_input_processor(settings, project_root=tmp_path)
