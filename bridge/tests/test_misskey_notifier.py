"""Test Misskey notifier service."""

import httpx
import pytest
import respx
from bridge.config import Settings
from bridge.services.misskey_notifier import MisskeyNotifier, ReplyResult


class TestMisskeyNotifier:
    """Tests for MisskeyNotifier."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            misskey_api_url="https://misskey.example.com/api",
            misskey_api_token="test-token",
        )

    @pytest.fixture
    def notifier(self, settings):
        """Create notifier instance."""
        return MisskeyNotifier(settings)

    def test_notes_create_url(self, notifier):
        """Test notes/create URL building."""
        assert notifier.notes_create_url == "https://misskey.example.com/api/notes/create"

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_reply_success(self, notifier):
        """Test successful reply posting."""
        respx.post("https://misskey.example.com/api/notes/create").mock(
            return_value=httpx.Response(200, json={
                "createdNote": {"id": "note456"}
            })
        )

        result = await notifier.post_reply(
            reply_to_id="note123",
            text="Test reply",
        )

        assert result.success
        assert result.note_id == "note456"
        assert result.status_code == 200

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_reply_api_error(self, notifier):
        """Test reply posting with API error."""
        respx.post("https://misskey.example.com/api/notes/create").mock(
            return_value=httpx.Response(400, json={
                "error": {"message": "Invalid token"}
            })
        )

        result = await notifier.post_reply(
            reply_to_id="note123",
            text="Test reply",
        )

        assert not result.success
        assert result.status_code == 400
        assert "Invalid token" in result.error

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_reply_timeout(self, notifier):
        """Test reply posting timeout."""
        respx.post("https://misskey.example.com/api/notes/create").mock(
            side_effect=httpx.TimeoutException("timeout")
        )

        result = await notifier.post_reply(
            reply_to_id="note123",
            text="Test reply",
        )

        assert not result.success
        assert "timed out" in result.error

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_reply_connection_error(self, notifier):
        """Test reply posting connection error."""
        respx.post("https://misskey.example.com/api/notes/create").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        result = await notifier.post_reply(
            reply_to_id="note123",
            text="Test reply",
        )

        assert not result.success
        assert "connect" in result.error.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_post_note_success(self, notifier):
        """Test successful note posting."""
        respx.post("https://misskey.example.com/api/notes/create").mock(
            return_value=httpx.Response(200, json={
                "createdNote": {"id": "note789"}
            })
        )

        result = await notifier.post_note(
            text="Test note",
            visibility="home",
        )

        assert result.success
        assert result.note_id == "note789"

    def test_post_reply_sync_success(self, notifier):
        """Test synchronous reply posting success."""
        with respx.mock:
            respx.post("https://misskey.example.com/api/notes/create").mock(
                return_value=httpx.Response(200, json={
                    "createdNote": {"id": "note456"}
                })
            )

            result = notifier.post_reply_sync(
                reply_to_id="note123",
                text="Test reply",
            )

            assert result.success
            assert result.note_id == "note456"