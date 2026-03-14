"""Kestra webhook trigger client.

Provides HTTP client for triggering Kestra flows via webhook triggers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from ..models.event import EventEnvelope


@dataclass
class KestraTriggerResult:
    """Result from triggering a Kestra flow.

    Attributes:
        success: Whether the trigger succeeded
        execution_id: Kestra execution ID if available
        error: Error message if trigger failed
        status_code: HTTP status code
    """

    success: bool
    execution_id: str | None = None
    error: str | None = None
    status_code: int = 0


class KestraClient:
    """Client for triggering Kestra flows via webhook triggers.

    Uses Kestra's webhook trigger API to start flow executions.
    """

    def __init__(self, settings: Settings):
        """Initialize client with settings.

        Args:
            settings: Application settings containing Kestra configuration
        """
        self.settings = settings
        self._webhook_url = settings.kestra_webhook_url
        self._basic_auth: httpx.BasicAuth | None = None
        if settings.has_basic_auth():
            self._basic_auth = httpx.BasicAuth(
                settings.kestra_basic_user,
                settings.kestra_basic_pass,
            )

    def build_payload(
        self,
        envelope: EventEnvelope,
        task_id: str,
        roadmap_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build payload for Kestra webhook trigger.

        Args:
            envelope: The event envelope
            task_id: The created task ID
            roadmap_request: The parsed roadmap request if available

        Returns:
            Payload dict for Kestra webhook
        """
        return {
            "event": envelope.event_type,
            "task_id": task_id,
            "trace_id": envelope.trace_id,
            "note_id": envelope.payload.get("note_id"),
            "command": envelope.payload.get("command"),
            "roadmap_request": roadmap_request,
            "reply_target": envelope.payload.get("note_id"),  # For reply
            "idempotency_key": envelope.idempotency_key,
            "actor": {
                "username": envelope.actor.username if envelope.actor else None,
                "user_id": envelope.actor.id if envelope.actor else None,
            },
            "timestamp": envelope.timestamp,
        }

    async def trigger_flow(
        self,
        payload: dict[str, Any],
        timeout: float = 30.0,
    ) -> KestraTriggerResult:
        """Trigger Kestra flow via webhook.

        Args:
            payload: The payload to send
            timeout: Request timeout in seconds

        Returns:
            KestraTriggerResult with trigger result
        """
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self._webhook_url,
                    json=payload,
                    auth=self._basic_auth,
                )

                if response.status_code >= 200 and response.status_code < 300:
                    # Success
                    data = response.json() if response.content else {}
                    return KestraTriggerResult(
                        success=True,
                        execution_id=data.get("id"),
                        status_code=response.status_code,
                    )
                else:
                    return KestraTriggerResult(
                        success=False,
                        error=f"Kestra returned {response.status_code}: {response.text[:500]}",
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException:
            return KestraTriggerResult(
                success=False,
                error="Kestra request timed out",
                status_code=0,
            )
        except httpx.ConnectError as e:
            return KestraTriggerResult(
                success=False,
                error=f"Failed to connect to Kestra: {e}",
                status_code=0,
            )
        except Exception as e:
            return KestraTriggerResult(
                success=False,
                error=f"Kestra trigger failed: {e}",
                status_code=0,
            )

    def trigger_flow_sync(
        self,
        payload: dict[str, Any],
        timeout: float = 30.0,
    ) -> KestraTriggerResult:
        """Trigger Kestra flow synchronously (for testing).

        Args:
            payload: The payload to send
            timeout: Request timeout in seconds

        Returns:
            KestraTriggerResult with trigger result
        """
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    self._webhook_url,
                    json=payload,
                    auth=self._basic_auth,
                )

                if response.status_code >= 200 and response.status_code < 300:
                    data = response.json() if response.content else {}
                    return KestraTriggerResult(
                        success=True,
                        execution_id=data.get("id"),
                        status_code=response.status_code,
                    )
                else:
                    return KestraTriggerResult(
                        success=False,
                        error=f"Kestra returned {response.status_code}: {response.text[:500]}",
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException:
            return KestraTriggerResult(
                success=False,
                error="Kestra request timed out",
                status_code=0,
            )
        except httpx.ConnectError as e:
            return KestraTriggerResult(
                success=False,
                error=f"Failed to connect to Kestra: {e}",
                status_code=0,
            )
        except Exception as e:
            return KestraTriggerResult(
                success=False,
                error=f"Kestra trigger failed: {e}",
                status_code=0,
            )