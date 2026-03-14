"""Misskey API client for posting replies.

Provides HTTP client for Misskey API interactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings


@dataclass
class ReplyResult:
    """Result from posting a reply to Misskey.

    Attributes:
        success: Whether the reply was posted successfully
        note_id: ID of the created note if successful
        error: Error message if failed
        status_code: HTTP status code
    """

    success: bool
    note_id: str | None = None
    error: str | None = None
    status_code: int = 0


class MisskeyNotifier:
    """Client for posting replies to Misskey via API.

    Uses Misskey's notes/create API endpoint.
    """

    def __init__(self, settings: Settings):
        """Initialize client with settings.

        Args:
            settings: Application settings containing Misskey API configuration
        """
        self.settings = settings
        # API base URL should be configured (e.g., https://misskey.example.com/api)
        self._api_url = getattr(settings, "misskey_api_url", "")
        self._api_token = getattr(settings, "misskey_api_token", "")

    @property
    def notes_create_url(self) -> str:
        """Get the notes/create API URL."""
        return f"{self._api_url.rstrip('/')}/notes/create"

    async def post_reply(
        self,
        *,
        reply_to_id: str,
        text: str,
        visibility: str = "home",
        cw: str | None = None,
    ) -> ReplyResult:
        """Post a reply note to Misskey.

        Args:
            reply_to_id: ID of the note to reply to
            text: Text content of the reply
            visibility: Note visibility (public, home, followers, specified)
            cw: Content warning if any

        Returns:
            ReplyResult with success status and created note ID
        """
        payload: dict[str, Any] = {
            "i": self._api_token,
            "replyId": reply_to_id,
            "text": text,
            "visibility": visibility,
        }

        if cw:
            payload["cw"] = cw

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.notes_create_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200 or response.status_code == 204:
                    data = response.json() if response.content else {}
                    return ReplyResult(
                        success=True,
                        note_id=data.get("createdNote", {}).get("id"),
                        status_code=response.status_code,
                    )
                else:
                    error_detail = ""
                    try:
                        error_detail = response.json().get("error", {}).get("message", "")
                    except Exception:
                        error_detail = response.text[:200]

                    return ReplyResult(
                        success=False,
                        error=f"Misskey API error {response.status_code}: {error_detail}",
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException:
            return ReplyResult(
                success=False,
                error="Misskey API request timed out",
                status_code=0,
            )
        except httpx.ConnectError as e:
            return ReplyResult(
                success=False,
                error=f"Failed to connect to Misskey: {e}",
                status_code=0,
            )
        except Exception as e:
            return ReplyResult(
                success=False,
                error=f"Failed to post reply: {e}",
                status_code=0,
            )

    async def post_note(
        self,
        *,
        text: str,
        visibility: str = "home",
        cw: str | None = None,
        reply_id: str | None = None,
        renote_id: str | None = None,
    ) -> ReplyResult:
        """Post a new note to Misskey.

        Args:
            text: Text content of the note
            visibility: Note visibility
            cw: Content warning if any
            reply_id: ID of note to reply to
            renote_id: ID of note to renote/quote

        Returns:
            ReplyResult with success status and created note ID
        """
        payload: dict[str, Any] = {
            "i": self._api_token,
            "text": text,
            "visibility": visibility,
        }

        if cw:
            payload["cw"] = cw
        if reply_id:
            payload["replyId"] = reply_id
        if renote_id:
            payload["renoteId"] = renote_id

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.notes_create_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200 or response.status_code == 204:
                    data = response.json() if response.content else {}
                    return ReplyResult(
                        success=True,
                        note_id=data.get("createdNote", {}).get("id"),
                        status_code=response.status_code,
                    )
                else:
                    error_detail = ""
                    try:
                        error_detail = response.json().get("error", {}).get("message", "")
                    except Exception:
                        error_detail = response.text[:200]

                    return ReplyResult(
                        success=False,
                        error=f"Misskey API error {response.status_code}: {error_detail}",
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException:
            return ReplyResult(
                success=False,
                error="Misskey API request timed out",
                status_code=0,
            )
        except httpx.ConnectError as e:
            return ReplyResult(
                success=False,
                error=f"Failed to connect to Misskey: {e}",
                status_code=0,
            )
        except Exception as e:
            return ReplyResult(
                success=False,
                error=f"Failed to post note: {e}",
                status_code=0,
            )

    def post_reply_sync(
        self,
        *,
        reply_to_id: str,
        text: str,
        visibility: str = "home",
    ) -> ReplyResult:
        """Post a reply note synchronously (for testing).

        Args:
            reply_to_id: ID of the note to reply to
            text: Text content of the reply
            visibility: Note visibility

        Returns:
            ReplyResult with success status
        """
        payload: dict[str, Any] = {
            "i": self._api_token,
            "replyId": reply_to_id,
            "text": text,
            "visibility": visibility,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    self.notes_create_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200 or response.status_code == 204:
                    data = response.json() if response.content else {}
                    return ReplyResult(
                        success=True,
                        note_id=data.get("createdNote", {}).get("id"),
                        status_code=response.status_code,
                    )
                else:
                    return ReplyResult(
                        success=False,
                        error=f"Misskey API error {response.status_code}",
                        status_code=response.status_code,
                    )

        except httpx.TimeoutException:
            return ReplyResult(
                success=False,
                error="Misskey API request timed out",
                status_code=0,
            )
        except Exception as e:
            return ReplyResult(
                success=False,
                error=f"Failed to post reply: {e}",
                status_code=0,
            )