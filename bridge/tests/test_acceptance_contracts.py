"""Acceptance-oriented tests for Phase 1 contracts."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from bridge.config import Settings
from bridge.main import create_app
from bridge.models.event import EventEnvelope
from bridge.services.misskey_notifier import MisskeyNotifier


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        misskey_hook_secret="test-secret",
        misskey_hook_secret_header="X-Misskey-Hook-Secret",
        taskstate_db="/tmp/test.db",
        taskstate_cli_path="",
        kestra_base_url="http://localhost:8080",
        kestra_namespace="pulse",
        kestra_flow_id="mention",
        kestra_webhook_key="test-key",
        misskey_api_url="https://misskey.example.com/api",
        misskey_api_token="test-token",
    )


@pytest.fixture
def client(test_settings: Settings):
    with patch("bridge.routers.webhooks.get_settings", return_value=test_settings):
        yield TestClient(create_app())


class TestEventEnvelopeContract:
    """EventEnvelope must satisfy the documented required fields."""

    def test_from_misskey_mention_sets_required_fields(self):
        envelope = EventEnvelope.from_misskey_mention(
            note_id="note123",
            note_text="@pulse roadmap",
            username="tester",
            user_id="user123",
            command="roadmap",
            roadmap_request={"goal": "Build app"},
        )

        assert envelope.event_id.startswith("evt_misskey_")
        assert envelope.event_type == "misskey.mention"
        assert envelope.source == "misskey"
        assert envelope.timestamp.endswith("Z")
        assert envelope.actor is not None
        assert envelope.actor.username == "tester"
        assert envelope.trace_id.startswith("trace_")
        assert envelope.payload["note_id"] == "note123"
        assert envelope.payload["command"] == "roadmap"
        assert envelope.idempotency_key == "misskey:note123"


class TestTraceIdObservability:
    """trace_id should be visible across bridge logging and Kestra payloads."""

    def test_trace_id_appears_in_key_bridge_logs(self, client, caplog):
        caplog.set_level("INFO")

        with patch("bridge.services.taskstate_gateway.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"ok": True, "data": {"id": "task123"}}),
                stderr="",
            )

            with respx.mock:
                respx.post("http://localhost:8080/api/v1/main/executions/webhook/pulse/mention/test-key").mock(
                    return_value=httpx.Response(200, json={"id": "exec123"})
                )

                response = client.post(
                    "/webhooks/misskey",
                    json={
                        "type": "mention",
                        "body": {
                            "note": {
                                "id": "note123",
                                "text": "@pulse roadmap\n```json\n{\"goal\": \"Build app\"}\n```",
                            },
                            "user": {"username": "tester", "id": "user123"},
                        },
                    },
                    headers={"X-Misskey-Hook-Secret": "test-secret"},
                )

        trace_id = response.json()["trace_id"]
        key_messages = {"Processing mention", "Task created", "Kestra flow triggered"}
        matching_records = [
            record for record in caplog.records
            if record.getMessage() in key_messages and getattr(record, "trace_id", None) == trace_id
        ]

        assert response.status_code == 202
        assert len(matching_records) == 3


class TestMisskeyReplyContract:
    """Misskey reply payload should match the documented reply contract."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_reply_sends_reply_id_text_and_visibility(self, test_settings: Settings):
        notifier = MisskeyNotifier(test_settings)
        captured_payload = {}

        def capture_payload(request: httpx.Request) -> httpx.Response:
            nonlocal captured_payload
            captured_payload = json.loads(request.content)
            return httpx.Response(200, json={"createdNote": {"id": "note456"}})

        respx.post("https://misskey.example.com/api/notes/create").mock(side_effect=capture_payload)

        result = await notifier.post_reply(
            reply_to_id="note123",
            text="Test reply",
            visibility="home",
        )

        assert result.success
        assert captured_payload == {
            "i": "test-token",
            "replyId": "note123",
            "text": "Test reply",
            "visibility": "home",
        }
