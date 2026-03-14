"""Misskey webhook payload models.

These models are designed to be tolerant of payload shape variations
since Misskey webhook payload format is not fully finalized.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class MisskeyUser(BaseModel):
    """Misskey user information."""

    id: Optional[str] = None
    username: Optional[str] = None
    name: Optional[str] = None
    host: Optional[str] = None

    model_config = {"extra": "allow"}


class MisskeyNote(BaseModel):
    """Misskey note information."""

    id: Optional[str] = None
    text: Optional[str] = None
    visibility: Optional[str] = None
    user: Optional[MisskeyUser] = None

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def extract_user(cls, data: Any) -> Any:
        """Extract user from nested structure if present."""
        if isinstance(data, dict):
            # Handle case where user is at body.note.user
            if "user" not in data and "username" in data:
                data["user"] = {"username": data.get("username"), "id": data.get("userId")}
        return data


class MisskeyWebhookPayload(BaseModel):
    """Misskey webhook payload.

    Tolerant parser for webhook payload. The actual shape varies
    depending on Misskey version and webhook configuration.

    Priority fields:
    - type: Event type (mention, reply, etc.)
    - body.note.id: Note ID
    - body.note.text: Note text
    - body.user.username: Username
    """

    type: Optional[str] = Field(None, description="Event type: mention, reply, etc.")
    body: Optional[dict[str, Any]] = Field(default_factory=dict, description="Event body")

    model_config = {"extra": "allow"}

    @property
    def event_type(self) -> str | None:
        """Get event type from payload."""
        return self.type

    @property
    def is_mention(self) -> bool:
        """Check if this is a mention event."""
        return self.type == "mention"

    @property
    def note(self) -> MisskeyNote | None:
        """Extract note from body."""
        if not self.body:
            return None

        note_data = self.body.get("note", {})
        if not note_data:
            return None

        # Merge user info from body level if note doesn't have it
        if "user" not in note_data:
            body_user = self.body.get("user", {})
            if body_user:
                note_data["user"] = body_user

        return MisskeyNote.model_validate(note_data)

    @property
    def note_id(self) -> str | None:
        """Get note ID."""
        note = self.note
        return note.id if note else None

    @property
    def note_text(self) -> str | None:
        """Get note text."""
        note = self.note
        return note.text if note else None

    @property
    def username(self) -> str | None:
        """Get username who triggered the event."""
        note = self.note
        if note and note.user:
            return note.user.username
        # Fallback to body level user
        if self.body:
            user = self.body.get("user", {})
            return user.get("username")
        return None

    @property
    def user_id(self) -> str | None:
        """Get user ID who triggered the event."""
        note = self.note
        if note and note.user:
            return note.user.id
        # Fallback to body level user
        if self.body:
            user = self.body.get("user", {})
            return user.get("id")
        return None