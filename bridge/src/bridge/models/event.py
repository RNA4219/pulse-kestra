"""EventEnvelope model for pulse-kestra."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ActorInfo(BaseModel):
    """Actor information for user-triggered events."""

    id: Optional[str] = None
    username: Optional[str] = None


class EventEnvelope(BaseModel):
    """Normalized event envelope for all entry events.

    All entry events (webhook, schedule, manual) are normalized to this format.
    """

    event_id: str = Field(..., description="Unique identifier for the event")
    event_type: str = Field(..., description="Event type like misskey.mention, manual, schedule")
    source: str = Field(..., description="Source system: misskey, kestra, manual")
    timestamp: str = Field(..., description="ISO8601 timestamp")
    actor: Optional[ActorInfo] = Field(None, description="Sender info for user-triggered events")
    payload: dict[str, Any] = Field(default_factory=dict, description="Minimal event content")
    trace_id: str = Field(..., description="Cross-component trace identifier")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key for deduplication")

    @classmethod
    def from_misskey_mention(
        cls,
        note_id: str,
        note_text: str,
        username: str | None,
        user_id: str | None,
        command: str,
        roadmap_request: dict[str, Any] | None = None,
    ) -> "EventEnvelope":
        """Create EventEnvelope from Misskey mention.

        Args:
            note_id: Misskey note ID
            note_text: Note text content
            username: Username who mentioned
            user_id: User ID who mentioned
            command: Extracted command (e.g., 'roadmap')
            roadmap_request: Parsed RoadmapRequest if available

        Returns:
            EventEnvelope instance
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        trace_id = f"trace_{uuid4().hex}"
        event_id = f"evt_misskey_{uuid4().hex[:12]}"

        return cls(
            event_id=event_id,
            event_type="misskey.mention",
            source="misskey",
            timestamp=now,
            actor=ActorInfo(id=user_id, username=username),
            payload={
                "note_id": note_id,
                "text": note_text,
                "command": command,
                "roadmap_request": roadmap_request,
            },
            trace_id=trace_id,
            idempotency_key=f"misskey:{note_id}",
        )