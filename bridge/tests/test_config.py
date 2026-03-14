"""Test configuration module."""

import sys
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


class TestTaskstateCliCommand:
    """Tests for taskstate CLI command building."""

    def test_default_uses_sys_executable(self):
        """Test that default path uses sys.executable."""
        settings = Settings(taskstate_db="/tmp/test.db")
        cmd = settings.taskstate_cli_command

        assert cmd[0] == sys.executable
        assert "agent-taskstate_cli.py" in cmd[1]
        assert "--db" in cmd
        assert "/tmp/test.db" in cmd

    def test_cli_path_with_py_file_uses_sys_executable(self):
        """Test that PULSE_TASKSTATE_CLI_PATH with .py file uses sys.executable.

        This is critical for Windows compatibility.
        """
        settings = Settings(
            taskstate_cli_path="/path/to/custom_cli.py",
            taskstate_db="/tmp/test.db",
        )
        cmd = settings.taskstate_cli_command

        # Must use sys.executable for .py files
        assert cmd[0] == sys.executable, "Python scripts must be run via sys.executable"
        # Path may be normalized on Windows, just check it ends with .py
        assert cmd[1].endswith(".py") or "custom_cli.py" in cmd[1]
        assert "--db" in cmd

    def test_cli_path_with_exe_runs_directly(self):
        """Test that PULSE_TASKSTATE_CLI_PATH with .exe file runs directly."""
        settings = Settings(
            taskstate_cli_path="/path/to/taskstate.exe",
            taskstate_db="/tmp/test.db",
        )
        cmd = settings.taskstate_cli_command

        # .exe files run directly (not via sys.executable)
        assert cmd[0] != sys.executable, ".exe files should not use sys.executable"
        assert ".exe" in cmd[0].lower() or "taskstate" in cmd[0].lower()
        assert "--db" in cmd

    def test_cli_path_relative_resolves_correctly(self):
        """Test that relative CLI path is resolved correctly."""
        settings = Settings(
            taskstate_cli_path="custom/cli.py",
            taskstate_db="/tmp/test.db",
        )
        cmd = settings.taskstate_cli_command

        # Relative .py path should still use sys.executable
        assert cmd[0] == sys.executable
        # Should contain the relative path (normalized)
        assert "cli.py" in cmd[1]

    def test_cli_path_windows_style_py_uses_sys_executable(self):
        """Test Windows-style path with .py uses sys.executable."""
        settings = Settings(
            taskstate_cli_path="C:\\Users\\test\\cli.py",
            taskstate_db="C:\\Users\\test\\db",
        )
        cmd = settings.taskstate_cli_command

        assert cmd[0] == sys.executable
        assert "cli.py" in cmd[1]