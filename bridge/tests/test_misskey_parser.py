"""Test Misskey parser service."""

import pytest
from bridge.models.misskey import MisskeyWebhookPayload
from bridge.services.misskey_parser import MisskeyParser, ParseResult


class TestMisskeyParser:
    """Tests for MisskeyParser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return MisskeyParser()

    def test_parse_non_mention(self, parser):
        """Test parsing a non-mention event."""
        payload = MisskeyWebhookPayload(type="reply", body={})
        result = parser.parse(payload)

        assert result.is_valid
        assert not result.is_mention

    def test_parse_mention_without_command(self, parser):
        """Test parsing a mention without @pulse command."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "Hello world!",
                },
                "user": {"username": "testuser"},
            },
        )
        result = parser.parse(payload)

        assert result.is_valid
        assert result.is_mention
        assert result.command is None
        assert result.note_id == "note123"
        assert result.username == "testuser"

    def test_parse_mention_with_unsupported_command(self, parser):
        """Test parsing a mention with unsupported command."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "@pulse unknown command",
                },
                "user": {"username": "testuser"},
            },
        )
        result = parser.parse(payload)

        assert result.is_valid
        assert result.is_mention
        assert result.command == "unknown"

    def test_parse_roadmap_without_json_block(self, parser):
        """Test parsing @pulse roadmap without JSON code block."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "@pulse roadmap please help me",
                },
                "user": {"username": "testuser"},
            },
        )
        result = parser.parse(payload)

        assert not result.is_valid
        assert result.is_mention
        assert result.command == "roadmap"
        assert result.error == "No JSON code block found"

    def test_parse_roadmap_with_invalid_json(self, parser):
        """Test parsing @pulse roadmap with invalid JSON."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "@pulse roadmap\n```json\n{invalid json}\n```",
                },
                "user": {"username": "testuser"},
            },
        )
        result = parser.parse(payload)

        assert not result.is_valid
        assert result.command == "roadmap"
        assert "Invalid JSON" in result.error

    def test_parse_roadmap_with_invalid_schema(self, parser):
        """Test parsing @pulse roadmap with invalid RoadmapRequest schema."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "@pulse roadmap\n```json\n{\"context\": \"test\"}\n```",
                },
                "user": {"username": "testuser"},
            },
        )
        result = parser.parse(payload)

        assert not result.is_valid
        assert result.command == "roadmap"
        assert "Invalid RoadmapRequest" in result.error

    def test_parse_roadmap_valid(self, parser):
        """Test parsing valid @pulse roadmap."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "@pulse roadmap\n```json\n{\"goal\": \"Build a web app\", \"deadline\": \"2026-06-01\"}\n```",
                },
                "user": {"username": "testuser", "id": "user123"},
            },
        )
        result = parser.parse(payload)

        assert result.is_valid
        assert result.is_mention
        assert result.command == "roadmap"
        assert result.roadmap_request is not None
        assert result.roadmap_request.goal == "Build a web app"
        assert result.roadmap_request.deadline == "2026-06-01"
        assert result.note_id == "note123"
        assert result.username == "testuser"
        assert result.user_id == "user123"

    def test_parse_mention_case_insensitive(self, parser):
        """Test that @pulse is case insensitive."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "@PULSE roadmap\n```json\n{\"goal\": \"test\"}\n```",
                },
            },
        )
        result = parser.parse(payload)

        assert result.command == "roadmap"

    def test_extract_json_block(self, parser):
        """Test JSON block extraction."""
        text = "Some text\n```json\n{\"key\": \"value\"}\n```\nMore text"
        result = parser.extract_json_block(text)

        assert result == {"key": "value"}

    def test_extract_json_block_none(self, parser):
        """Test JSON block extraction when none present."""
        text = "Some text without code block"
        result = parser.extract_json_block(text)

        assert result is None


class TestMisskeyWebhookPayload:
    """Tests for MisskeyWebhookPayload model."""

    def test_is_mention(self):
        """Test is_mention property."""
        payload = MisskeyWebhookPayload(type="mention", body={})
        assert payload.is_mention

        payload = MisskeyWebhookPayload(type="reply", body={})
        assert not payload.is_mention

    def test_note_extraction(self):
        """Test note extraction from body."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "Hello",
                    "user": {"username": "testuser"},
                },
            },
        )

        assert payload.note_id == "note123"
        assert payload.note_text == "Hello"
        assert payload.username == "testuser"

    def test_tolerant_parsing(self):
        """Test that parser is tolerant of unknown fields."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "Hello",
                    "unknown_field": "value",
                },
                "extra_data": {"foo": "bar"},
            },
        )

        # Should not raise
        assert payload.note_id == "note123"

    def test_user_at_body_level(self):
        """Test user info at body level (fallback)."""
        payload = MisskeyWebhookPayload(
            type="mention",
            body={
                "note": {
                    "id": "note123",
                    "text": "Hello",
                },
                "user": {"username": "bodyuser", "id": "bodyid"},
            },
        )

        assert payload.username == "bodyuser"
        assert payload.user_id == "bodyid"