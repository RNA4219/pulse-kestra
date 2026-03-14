"""Misskey webhook endpoint.

Handles POST /webhooks/misskey with secret validation, mention parsing,
task creation, and Kestra flow triggering.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from ..config import Settings, get_settings
from ..models.event import EventEnvelope
from ..models.misskey import MisskeyWebhookPayload
from ..services import InputGuard, KestraClient, MisskeyParser, TaskstateGateway
from ..services.input_guard import GuardDecision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _get_settings() -> Settings:
    """Get settings instance."""
    return get_settings()


@router.post("/misskey")
async def handle_misskey_webhook(
    request: Request,
    settings: Settings = Depends(_get_settings),
) -> Response:
    """Handle Misskey webhook.

    Expected responses:
    - 401: Secret mismatch
    - 204: Non-target event, not a mention, or unsupported command
    - 422: roadmap command but missing/invalid JSON code block
    - 202: Successfully accepted
    - 502: Taskstate or Kestra call failed

    Args:
        request: The HTTP request
        settings: Application settings

    Returns:
        HTTP response
    """
    # 1. Validate secret
    secret_header = settings.misskey_hook_secret_header
    provided_secret = request.headers.get(secret_header, "")

    if not _validate_secret(provided_secret, settings.misskey_hook_secret):
        logger.warning(
            "Webhook secret mismatch",
            extra={"header": secret_header, "provided": bool(provided_secret)},
        )
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # 2. Parse payload
    try:
        body = await request.json()
    except Exception as e:
        logger.warning("Failed to parse webhook body", extra={"error": str(e)})
        return Response(status_code=204)

    payload = MisskeyWebhookPayload.model_validate(body)

    # 3. Parse mention
    parser = MisskeyParser()
    result = parser.parse(payload)

    # Not a mention
    if not result.is_mention:
        logger.debug("Ignoring non-mention event", extra={"type": payload.event_type})
        return Response(status_code=204)

    # No command found
    if not result.command:
        logger.debug("Ignoring mention without @pulse command")
        return Response(status_code=204)

    # 3b. Input guard check (FR-010, FR-011, FR-012)
    guard = InputGuard()
    note_text = result.note_text or ""
    guard_result = guard.check(note_text)

    if guard_result.is_reject:
        logger.warning(
            "Input rejected by guard",
            extra={
                "note_id": result.note_id,
                "reason": guard_result.reason,
                "patterns": guard_result.matched_patterns,
            },
        )
        # Create taskstate record for guard rejection
        # Must follow valid state transitions: draft → ready → in_progress → review
        gateway = TaskstateGateway(settings)
        envelope = EventEnvelope.from_misskey_mention(
            note_id=result.note_id or "",
            note_text=result.note_text or "",
            username=result.username,
            user_id=result.user_id,
            command=result.command or "",
            roadmap_request=None,
        )

        task_result = gateway.create_task_for_mention(
            trace_id=envelope.trace_id,
            note_id=result.note_id or "",
            username=result.username,
            command=result.command or "guard_rejected",
        )

        if task_result.success and task_result.data:
            task_id = task_result.data.get("id")
            if task_id:
                # Follow valid state transitions: draft → ready → in_progress → review
                # Step 1: draft → ready
                ready_result = gateway.set_status(
                    task_id=task_id,
                    status="ready",
                    reason=f"Guard rejected: {guard_result.reason}",
                )
                if not ready_result.success:
                    logger.error(
                        "Failed to set guard rejection task to ready",
                        extra={
                            "task_id": task_id,
                            "error": ready_result.error,
                        },
                    )
                    # Continue anyway to log what we can

                # Step 2: ready → in_progress
                in_progress_result = gateway.set_status(
                    task_id=task_id,
                    status="in_progress",
                    reason="Processing guard rejection",
                )
                if not in_progress_result.success:
                    logger.error(
                        "Failed to set guard rejection task to in_progress",
                        extra={
                            "task_id": task_id,
                            "error": in_progress_result.error,
                        },
                    )

                # Step 3: in_progress → review
                review_result = gateway.set_status(
                    task_id=task_id,
                    status="review",
                    reason=f"Guard rejected: {guard_result.reason}",
                )
                if review_result.success:
                    logger.info(
                        "Guard rejection recorded in taskstate with review status",
                        extra={
                            "task_id": task_id,
                            "trace_id": envelope.trace_id,
                            "reason": guard_result.reason,
                        },
                    )
                else:
                    logger.error(
                        "Failed to set guard rejection task to review",
                        extra={
                            "task_id": task_id,
                            "error": review_result.error,
                        },
                    )

        raise HTTPException(status_code=400, detail=guard_result.reason)

    if guard_result.needs_review:
        logger.warning(
            "Input needs review",
            extra={
                "note_id": result.note_id,
                "reason": guard_result.reason,
                "patterns": guard_result.matched_patterns,
            },
        )
        # For Phase 1, we still process but log the concern
        # In Phase 2, this could create task with needs_review status

    if guard_result.decision == GuardDecision.LOG_ONLY:
        logger.info(
            "Input has unusual patterns",
            extra={
                "note_id": result.note_id,
                "reason": guard_result.reason,
                "patterns": guard_result.matched_patterns,
            },
        )

    # Unsupported command (not roadmap)
    if result.command != "roadmap":
        logger.debug(
            "Ignoring unsupported command",
            extra={"command": result.command},
        )
        return Response(status_code=204)

    # roadmap command but invalid
    if not result.is_valid:
        logger.warning(
            "Invalid roadmap request",
            extra={"error": result.error, "note_id": result.note_id},
        )
        raise HTTPException(status_code=422, detail=result.error)

    # 4. Create EventEnvelope
    roadmap_request_dict = None
    if result.roadmap_request:
        roadmap_request_dict = result.roadmap_request.model_dump()

    envelope = EventEnvelope.from_misskey_mention(
        note_id=result.note_id or "",
        note_text=result.note_text or "",
        username=result.username,
        user_id=result.user_id,
        command=result.command,
        roadmap_request=roadmap_request_dict,
    )

    logger.info(
        "Processing mention",
        extra={
            "trace_id": envelope.trace_id,
            "note_id": result.note_id,
            "command": result.command,
        },
    )

    # 5. Create task in taskstate
    gateway = TaskstateGateway(settings)
    task_result = gateway.create_task_for_mention(
        trace_id=envelope.trace_id,
        note_id=result.note_id or "",
        username=result.username,
        command=result.command,
    )

    if not task_result.success:
        logger.error(
            "Failed to create task",
            extra={
                "trace_id": envelope.trace_id,
                "error": task_result.error,
            },
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create task: {task_result.error}",
        )

    task_id = task_result.data.get("id") if task_result.data else None
    if not task_id:
        logger.error(
            "Task ID not returned",
            extra={"trace_id": envelope.trace_id, "data": task_result.data},
        )
        raise HTTPException(
            status_code=502,
            detail="Task created but ID not returned",
        )

    logger.info(
        "Task created",
        extra={"trace_id": envelope.trace_id, "task_id": task_id},
    )

    # 6. Put initial state
    state_result = gateway.put_state(
        task_id=task_id,
        current_step="Task created, waiting for worker execution",
        constraints=[],
        done_when=["Worker execution completed", "Reply sent"],
        confidence="medium",
    )

    if not state_result.success:
        logger.error(
            "Failed to put state",
            extra={"trace_id": envelope.trace_id, "task_id": task_id, "error": state_result.error},
        )
        # Phase 1 contract: state put is required before Kestra trigger
        raise HTTPException(
            status_code=502,
            detail=f"Failed to put state: {state_result.error}",
        )

    # 7. Set status to ready (maps to queued)
    status_result = gateway.set_status(
        task_id=task_id,
        status="ready",
        reason="Task ready for processing",
    )

    if not status_result.success:
        logger.error(
            "Failed to set status",
            extra={"trace_id": envelope.trace_id, "task_id": task_id, "error": status_result.error},
        )
        # Phase 1 contract: status ready is required before Kestra trigger
        raise HTTPException(
            status_code=502,
            detail=f"Failed to set status: {status_result.error}",
        )

    # 8. Trigger Kestra flow
    kestra_client = KestraClient(settings)
    kestra_payload = kestra_client.build_payload(
        envelope=envelope,
        task_id=task_id,
        roadmap_request=roadmap_request_dict,
    )

    kestra_result = await kestra_client.trigger_flow(kestra_payload)

    if not kestra_result.success:
        logger.error(
            "Failed to trigger Kestra flow",
            extra={
                "trace_id": envelope.trace_id,
                "task_id": task_id,
                "error": kestra_result.error,
            },
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to trigger Kestra: {kestra_result.error}",
        )

    logger.info(
        "Kestra flow triggered",
        extra={
            "trace_id": envelope.trace_id,
            "task_id": task_id,
            "execution_id": kestra_result.execution_id,
        },
    )

    # 9. Return success
    return JSONResponse(
        status_code=202,
        content={"status": "accepted", "task_id": task_id, "trace_id": envelope.trace_id},
    )


def _validate_secret(provided: str, expected: str) -> bool:
    """Validate webhook secret using constant-time comparison.

    Args:
        provided: Secret from request header
        expected: Expected secret from settings

    Returns:
        True if secrets match
    """
    import secrets

    if not expected:
        # No secret configured - reject all
        return False

    return secrets.compare_digest(provided, expected)