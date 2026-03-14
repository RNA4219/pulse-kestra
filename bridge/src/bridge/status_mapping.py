"""Status mapping between logical states and taskstate states.

This module defines the mapping between logical task states used in
pulse-kestra and the actual taskstate status values.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class LogicalStatus(str, Enum):
    """Logical task status used in pulse-kestra.

    These are the user-facing states that abstract away
    the taskstate implementation details.
    """

    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    NEEDS_REVIEW = "needs_review"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskstateStatus(str, Enum):
    """Taskstate status values from agent-taskstate CLI.

    These are the actual status values stored in taskstate.
    """

    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    REVIEW = "review"
    DONE = "done"
    ARCHIVED = "archived"


class RunStatus(str, Enum):
    """Run status values from agent-taskstate."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Mapping from logical status to taskstate status
# Each logical status maps to a combination of task status + optional run status
LOGICAL_TO_TASKSTATE: dict[LogicalStatus, dict[str, Any]] = {
    LogicalStatus.QUEUED: {
        "task_status": TaskstateStatus.READY,
        "run_status": None,
    },
    LogicalStatus.RUNNING: {
        "task_status": TaskstateStatus.IN_PROGRESS,
        "run_status": RunStatus.RUNNING,
    },
    LogicalStatus.WAITING: {
        "task_status": TaskstateStatus.BLOCKED,
        "run_status": None,
    },
    LogicalStatus.NEEDS_REVIEW: {
        "task_status": TaskstateStatus.REVIEW,
        "run_status": None,
    },
    LogicalStatus.DONE: {
        "task_status": TaskstateStatus.DONE,
        "run_status": RunStatus.SUCCEEDED,
    },
    LogicalStatus.FAILED: {
        "task_status": TaskstateStatus.REVIEW,
        "run_status": RunStatus.FAILED,
    },
    LogicalStatus.CANCELLED: {
        "task_status": TaskstateStatus.ARCHIVED,
        "run_status": RunStatus.CANCELLED,
    },
}


def logical_to_taskstate(logical: LogicalStatus) -> dict[str, Any]:
    """Convert logical status to taskstate status.

    Args:
        logical: The logical status

    Returns:
        Dict with task_status and optional run_status
    """
    return LOGICAL_TO_TASKSTATE.get(logical, {})


def taskstate_to_logical(
    task_status: str,
    run_status: str | None = None,
) -> LogicalStatus | None:
    """Convert taskstate status to logical status.

    Args:
        task_status: Task status from taskstate
        run_status: Optional run status from taskstate

    Returns:
        Logical status or None if no match
    """
    # Check combinations first (for running, done, failed, cancelled)
    if task_status == TaskstateStatus.IN_PROGRESS.value:
        if run_status == RunStatus.RUNNING.value:
            return LogicalStatus.RUNNING
        return LogicalStatus.RUNNING  # Default for in_progress

    if task_status == TaskstateStatus.DONE.value:
        if run_status == RunStatus.SUCCEEDED.value or run_status is None:
            return LogicalStatus.DONE

    if task_status == TaskstateStatus.REVIEW.value:
        if run_status == RunStatus.FAILED.value:
            return LogicalStatus.FAILED
        return LogicalStatus.NEEDS_REVIEW

    if task_status == TaskstateStatus.ARCHIVED.value:
        if run_status == RunStatus.CANCELLED.value:
            return LogicalStatus.CANCELLED
        return LogicalStatus.CANCELLED  # Default for archived

    # Simple mappings
    if task_status == TaskstateStatus.READY.value:
        return LogicalStatus.QUEUED

    if task_status == TaskstateStatus.BLOCKED.value:
        return LogicalStatus.WAITING

    return None