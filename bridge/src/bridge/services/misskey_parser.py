"""Misskey mention parser service.

Handles mention detection, command extraction, and JSON code block parsing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ..models.misskey import MisskeyWebhookPayload
from ..models.roadmap import RoadmapRequest


@dataclass
class ParseResult:
    """Result of parsing a Misskey webhook payload.

    Attributes:
        is_valid: Whether the payload is valid for processing
        is_mention: Whether this is a mention event
        command: Extracted command (e.g., 'roadmap') or None
        roadmap_request: Parsed RoadmapRequest if available
        note_id: Note ID from the payload
        note_text: Note text from the payload
        username: Username who sent the mention
        user_id: User ID who sent the mention
        error: Error message if parsing failed
    """

    is_valid: bool
    is_mention: bool = False
    command: str | None = None
    roadmap_request: RoadmapRequest | None = None
    note_id: str | None = None
    note_text: str | None = None
    username: str | None = None
    user_id: str | None = None
    error: str | None = None


class MisskeyParser:
    """Parser for Misskey webhook payloads.

    Responsible for:
    - Detecting mention events
    - Extracting @pulse commands
    - Parsing JSON code blocks as RoadmapRequest
    """

    # Command pattern: @pulse <command>
    COMMAND_PATTERN = re.compile(r"@pulse\s+(\w+)", re.IGNORECASE)
    # JSON code block pattern: ```json ... ```
    JSON_BLOCK_PATTERN = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)

    def __init__(self, bot_name: str = "pulse"):
        """Initialize parser.

        Args:
            bot_name: The bot name to look for in mentions (default: pulse)
        """
        self.bot_name = bot_name

    def parse(self, payload: MisskeyWebhookPayload) -> ParseResult:
        """Parse a Misskey webhook payload.

        Args:
            payload: The webhook payload to parse

        Returns:
            ParseResult with extraction results
        """
        # Check if this is a mention
        if not payload.is_mention:
            return ParseResult(is_valid=True, is_mention=False)

        # Extract note information
        note_text = payload.note_text
        note_id = payload.note_id
        username = payload.username
        user_id = payload.user_id

        if not note_text:
            return ParseResult(
                is_valid=True,
                is_mention=True,
                note_id=note_id,
                username=username,
                user_id=user_id,
            )

        # Extract command
        command = self._extract_command(note_text)

        if not command:
            # Mention without @pulse command
            return ParseResult(
                is_valid=True,
                is_mention=True,
                note_id=note_id,
                note_text=note_text,
                username=username,
                user_id=user_id,
            )

        # Handle roadmap command
        if command == "roadmap":
            roadmap_request, error = self._parse_roadmap_request(note_text)
            if error:
                return ParseResult(
                    is_valid=False,
                    is_mention=True,
                    command=command,
                    note_id=note_id,
                    note_text=note_text,
                    username=username,
                    user_id=user_id,
                    error=error,
                )
            return ParseResult(
                is_valid=True,
                is_mention=True,
                command=command,
                roadmap_request=roadmap_request,
                note_id=note_id,
                note_text=note_text,
                username=username,
                user_id=user_id,
            )

        # Unsupported command
        return ParseResult(
            is_valid=True,
            is_mention=True,
            command=command,
            note_id=note_id,
            note_text=note_text,
            username=username,
            user_id=user_id,
        )

    def _extract_command(self, text: str) -> str | None:
        """Extract command from mention text.

        Args:
            text: The note text

        Returns:
            Command string or None
        """
        match = self.COMMAND_PATTERN.search(text)
        if match:
            return match.group(1).lower()
        return None

    def _parse_roadmap_request(self, text: str) -> tuple[RoadmapRequest | None, str | None]:
        """Parse roadmap request from note text.

        Args:
            text: The note text containing JSON code block

        Returns:
            Tuple of (RoadmapRequest or None, error message or None)
        """
        match = self.JSON_BLOCK_PATTERN.search(text)
        if not match:
            return None, "No JSON code block found"

        json_str = match.group(1)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON: {e.msg}"

        try:
            roadmap_request = RoadmapRequest.model_validate(data)
            return roadmap_request, None
        except ValidationError as e:
            return None, f"Invalid RoadmapRequest: {e}"

    def extract_json_block(self, text: str) -> dict[str, Any] | None:
        """Extract first JSON code block from text.

        Args:
            text: The note text

        Returns:
            Parsed JSON dict or None
        """
        match = self.JSON_BLOCK_PATTERN.search(text)
        if not match:
            return None

        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None