import pytest

from local_ai_agent.config import Settings


def test_settings_validation_allows_stub_without_api_key():
    settings = Settings(provider="stub", api_key=None)

    assert settings.provider == "stub"


def test_settings_validation_rejects_real_provider_without_api_key():
    with pytest.raises(ValueError, match="api_key"):
        Settings(provider="cerebras", api_key=None)
