"""Test configuration and fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# We'll use these fixtures across tests


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    from bridge.config import Settings

    return Settings(
        misskey_hook_secret="test-secret",
        misskey_hook_secret_header="X-Misskey-Hook-Secret",
        taskstate_db="/tmp/test.db",
        taskstate_cli_path="",
        kestra_base_url="http://localhost:8080",
        kestra_namespace="pulse",
        kestra_flow_id="mention",
        kestra_webhook_key="test-key",
        kestra_basic_user="",
        kestra_basic_pass="",
    )