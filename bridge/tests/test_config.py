"""Test configuration module."""

import pytest
from bridge.config import Settings, get_settings


def test_settings_defaults():
    """Test that settings have sensible defaults."""
    settings = Settings()

    assert settings.misskey_hook_secret_header == "X-Misskey-Hook-Secret"
    assert settings.misskey_hook_secret == ""
    assert settings.taskstate_db == ""
    assert settings.kestra_base_url == ""


def test_settings_from_env(monkeypatch):
    """Test loading settings from environment variables."""
    monkeypatch.setenv("PULSE_MISSKEY_HOOK_SECRET", "my-secret")
    monkeypatch.setenv("PULSE_KESTRA_BASE_URL", "http://kestra:8080")

    settings = Settings()

    assert settings.misskey_hook_secret == "my-secret"
    assert settings.kestra_base_url == "http://kestra:8080"


def test_kestra_webhook_url():
    """Test Kestra webhook URL building."""
    settings = Settings(
        kestra_base_url="http://localhost:8080/",
        kestra_namespace="pulse",
        kestra_flow_id="mention",
        kestra_webhook_key="test-key",
    )

    assert settings.kestra_webhook_url == "http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key"


def test_has_basic_auth():
    """Test Basic Auth detection."""
    settings = Settings()
    assert not settings.has_basic_auth()

    settings = Settings(kestra_basic_user="user", kestra_basic_pass="")
    assert not settings.has_basic_auth()

    settings = Settings(kestra_basic_user="user", kestra_basic_pass="pass")
    assert settings.has_basic_auth()


def test_get_settings_caches():
    """Test that get_settings caches the result."""
    # Clear cache first
    get_settings.cache_clear()

    s1 = get_settings()
    s2 = get_settings()

    assert s1 is s2