"""Test KestraClient."""

import httpx
import pytest
import respx
from bridge.config import Settings
from bridge.services.kestra_client import KestraClient, KestraTriggerResult
from bridge.models.event import EventEnvelope, ActorInfo


class TestKestraClient:
    """Tests for KestraClient."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            kestra_base_url="http://localhost:8080",
            kestra_namespace="pulse",
            kestra_flow_id="mention",
            kestra_webhook_key="test-key",
            kestra_basic_user="",
            kestra_basic_pass="",
        )

    @pytest.fixture
    def settings_with_auth(self):
        """Create test settings with Basic Auth."""
        return Settings(
            kestra_base_url="http://localhost:8080",
            kestra_namespace="pulse",
            kestra_flow_id="mention",
            kestra_webhook_key="test-key",
            kestra_basic_user="testuser",
            kestra_basic_pass="testpass",
        )

    @pytest.fixture
    def client(self, settings):
        """Create client instance."""
        return KestraClient(settings)

    def test_webhook_url_building(self, settings):
        """Test that webhook URL is built correctly."""
        client = KestraClient(settings)

        expected_url = "http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key"
        assert client._webhook_url == expected_url

    def test_basic_auth_configured(self, settings_with_auth):
        """Test that Basic Auth is configured when credentials are provided."""
        client = KestraClient(settings_with_auth)

        assert client._basic_auth is not None

    def test_no_basic_auth(self, settings):
        """Test that Basic Auth is None when credentials are not provided."""
        client = KestraClient(settings)

        assert client._basic_auth is None

    def test_build_payload(self, client):
        """Test payload building."""
        envelope = EventEnvelope(
            event_id="evt123",
            event_type="misskey.mention",
            source="misskey",
            timestamp="2026-03-14T10:00:00Z",
            actor=ActorInfo(id="user123", username="testuser"),
            payload={
                "note_id": "note123",
                "text": "@pulse roadmap",
                "command": "roadmap",
            },
            trace_id="trace123",
            idempotency_key="misskey:note123",
        )

        payload = client.build_payload(
            envelope=envelope,
            task_id="task123",
            roadmap_request={"goal": "Build app"},
        )

        assert payload["event"] == "misskey.mention"
        assert payload["task_id"] == "task123"
        assert payload["trace_id"] == "trace123"
        assert payload["note_id"] == "note123"
        assert payload["command"] == "roadmap"
        assert payload["roadmap_request"] == {"goal": "Build app"}
        assert payload["reply_target"] == "note123"
        assert payload["idempotency_key"] == "misskey:note123"
        assert payload["actor"]["username"] == "testuser"
        assert payload["actor"]["user_id"] == "user123"

    @respx.mock
    @pytest.mark.asyncio
    async def test_trigger_flow_success(self, client):
        """Test successful flow trigger."""
        respx.post("http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key").mock(
            return_value=httpx.Response(200, json={"id": "exec123"})
        )

        result = await client.trigger_flow({"test": "data"})

        assert result.success
        assert result.execution_id == "exec123"
        assert result.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_trigger_flow_failure(self, client):
        """Test failed flow trigger."""
        respx.post("http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        result = await client.trigger_flow({"test": "data"})

        assert not result.success
        assert result.status_code == 500
        assert "500" in result.error

    @respx.mock
    @pytest.mark.asyncio
    async def test_trigger_flow_timeout(self, client):
        """Test flow trigger timeout."""
        respx.post("http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        result = await client.trigger_flow({"test": "data"})

        assert not result.success
        assert "timed out" in result.error

    @respx.mock
    @pytest.mark.asyncio
    async def test_trigger_flow_connection_error(self, client):
        """Test flow trigger connection error."""
        respx.post("http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        result = await client.trigger_flow({"test": "data"})

        assert not result.success
        assert "connect" in result.error.lower()

    def test_trigger_flow_sync_success(self, client):
        """Test synchronous flow trigger success."""
        with respx.mock:
            respx.post("http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key").mock(
                return_value=httpx.Response(200, json={"id": "exec123"})
            )

            result = client.trigger_flow_sync({"test": "data"})

            assert result.success
            assert result.execution_id == "exec123"