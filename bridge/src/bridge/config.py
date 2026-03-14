"""Configuration for pulse-bridge using pydantic-settings."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="PULSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Misskey webhook settings
    misskey_hook_secret: str = ""
    misskey_hook_secret_header: str = "X-Misskey-Hook-Secret"

    # Misskey API settings (for reply notifier)
    misskey_api_url: str = ""
    misskey_api_token: str = ""

    # Taskstate settings
    taskstate_db: str = ""
    taskstate_cli_path: str = ""

    # Kestra settings
    kestra_base_url: str = ""
    kestra_namespace: str = ""
    kestra_flow_id: str = ""
    kestra_webhook_key: str = ""
    kestra_basic_user: str = ""
    kestra_basic_pass: str = ""

    @property
    def taskstate_cli_command(self) -> list[str]:
        """Build taskstate CLI command.

        Contract: sys.executable + agent-taskstate_cli.py --db {db}

        If PULSE_TASKSTATE_CLI_PATH is specified and ends with .py,
        always use sys.executable to run it (for Windows compatibility).
        For other executables (.exe, etc.), use the path directly.
        """
        cli_path: Path

        if self.taskstate_cli_path:
            cli_path = Path(self.taskstate_cli_path)
            if not cli_path.is_absolute():
                # Relative path from repo root
                cli_path = Path(__file__).parent.parent.parent.parent.parent / cli_path
        else:
            # Default path
            cli_path = (
                Path(__file__).parent.parent.parent.parent.parent
                / "agent-taskstate" / "docs" / "src" / "agent-taskstate_cli.py"
            )

        # Always use sys.executable for Python scripts (Windows compatibility)
        if str(cli_path).endswith(".py"):
            return [sys.executable, str(cli_path), "--db", self.taskstate_db]
        else:
            # For .exe or other executables, run directly
            return [str(cli_path), "--db", self.taskstate_db]

    @property
    def kestra_webhook_url(self) -> str:
        """Build Kestra webhook trigger URL.

        Format: {base_url}/api/v1/main/executions/webhook/{namespace}/{flowId}/{key}
        """
        return (
            f"{self.kestra_base_url.rstrip('/')}"
            f"/api/v1/main/executions/webhook"
            f"/{self.kestra_namespace}"
            f"/{self.kestra_flow_id}"
            f"/{self.kestra_webhook_key}"
        )

    def has_basic_auth(self) -> bool:
        """Check if Basic Auth credentials are configured."""
        return bool(self.kestra_basic_user and self.kestra_basic_pass)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()