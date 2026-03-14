"""Taskstate gateway for agent-taskstate CLI integration.

Provides a subprocess gateway to interact with agent-taskstate CLI.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any

from ..config import Settings


@dataclass
class TaskstateResult:
    """Result from a taskstate CLI command.

    Attributes:
        success: Whether the command succeeded
        data: Parsed JSON output from the command
        error: Error message if command failed
        return_code: CLI process return code
    """

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    return_code: int = 0


class TaskstateGateway:
    """Gateway to agent-taskstate CLI.

    Provides methods to create tasks, put state, and set status.
    """

    def __init__(self, settings: Settings):
        """Initialize gateway with settings.

        Args:
            settings: Application settings containing CLI configuration
        """
        self.settings = settings
        self._cli_command = settings.taskstate_cli_command

    def _run_cli(self, args: list[str]) -> TaskstateResult:
        """Run taskstate CLI with given arguments.

        Args:
            args: CLI arguments (without the base command)

        Returns:
            TaskstateResult with success status and output
        """
        cmd = self._cli_command + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return TaskstateResult(
                    success=False,
                    error=result.stderr.strip() or f"CLI exited with code {result.returncode}",
                    return_code=result.returncode,
                )

            # Parse JSON output
            try:
                output = json.loads(result.stdout)
                if output.get("ok"):
                    return TaskstateResult(
                        success=True,
                        data=output.get("data"),
                        return_code=0,
                    )
                else:
                    return TaskstateResult(
                        success=False,
                        error=output.get("error", "Unknown error"),
                        return_code=result.returncode,
                    )
            except json.JSONDecodeError as e:
                return TaskstateResult(
                    success=False,
                    error=f"Failed to parse CLI output: {e}",
                    return_code=result.returncode,
                )

        except subprocess.TimeoutExpired:
            return TaskstateResult(
                success=False,
                error="CLI command timed out",
                return_code=-1,
            )
        except FileNotFoundError:
            return TaskstateResult(
                success=False,
                error=f"CLI not found: {self._cli_command[0]}",
                return_code=-1,
            )
        except Exception as e:
            return TaskstateResult(
                success=False,
                error=f"CLI execution failed: {e}",
                return_code=-1,
            )

    def create_task(
        self,
        *,
        task_id: str | None = None,
        kind: str = "feature",
        title: str,
        goal: str,
        priority: str = "medium",
        owner_type: str = "agent",
        owner_id: str | None = None,
    ) -> TaskstateResult:
        """Create a new task.

        Args:
            task_id: Optional task ID (auto-generated if not provided)
            kind: Task kind (bugfix, feature, research)
            title: Task title
            goal: Task goal
            priority: Task priority (low, medium, high, critical)
            owner_type: Owner type (human, agent, system)
            owner_id: Owner ID

        Returns:
            TaskstateResult with created task data
        """
        payload: dict[str, Any] = {
            "kind": kind,
            "title": title,
            "goal": goal,
            "priority": priority,
            "owner_type": owner_type,
            "status": "draft",
        }

        if task_id:
            payload["id"] = task_id
        if owner_id:
            payload["owner_id"] = owner_id

        args = ["task", "create", "--json", json.dumps(payload)]
        return self._run_cli(args)

    def put_state(
        self,
        *,
        task_id: str,
        current_step: str,
        constraints: list[str] | None = None,
        done_when: list[str] | None = None,
        current_summary: str | None = None,
        artifact_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        confidence: str = "medium",
        context_policy: dict[str, Any] | None = None,
    ) -> TaskstateResult:
        """Put task state.

        Args:
            task_id: Task ID
            current_step: Current step description
            constraints: List of constraints
            done_when: List of completion conditions
            current_summary: Current summary
            artifact_refs: List of artifact references
            evidence_refs: List of evidence references
            confidence: Confidence level (low, medium, high)
            context_policy: Context policy dict

        Returns:
            TaskstateResult with state data
        """
        payload: dict[str, Any] = {
            "current_step": current_step,
            "constraints": constraints or [],
            "done_when": done_when or [],
            "artifact_refs": artifact_refs or [],
            "evidence_refs": evidence_refs or [],
            "confidence": confidence,
            "context_policy": context_policy or {},
        }

        if current_summary:
            payload["current_summary"] = current_summary

        args = ["state", "put", "--task", task_id, "--json", json.dumps(payload)]
        return self._run_cli(args)

    def set_status(
        self,
        *,
        task_id: str,
        status: str,
        reason: str | None = None,
    ) -> TaskstateResult:
        """Set task status.

        Args:
            task_id: Task ID
            status: New status (draft, ready, in_progress, blocked, review, done, archived)
            reason: Reason for status change (required for some transitions)

        Returns:
            TaskstateResult with updated task data
        """
        args = ["task", "set-status", "--task", task_id, "--to", status]
        if reason:
            args.extend(["--reason", reason])
        return self._run_cli(args)

    def create_task_for_mention(
        self,
        *,
        trace_id: str,
        note_id: str,
        username: str | None,
        command: str,
    ) -> TaskstateResult:
        """Create a task for a Misskey mention.

        This is a convenience method that creates a task with sensible defaults
        for Misskey mention handling.

        Args:
            trace_id: Trace ID for correlation
            note_id: Misskey note ID
            username: Username who sent the mention
            command: Command extracted from mention

        Returns:
            TaskstateResult with created task data
        """
        title = f"Misskey mention: @{username or 'unknown'} - {command}"
        goal = f"Process @pulse {command} command from note {note_id}"

        return self.create_task(
            kind="feature",
            title=title,
            goal=goal,
            priority="medium",
            owner_type="agent",
            owner_id="pulse-bridge",
        )

    def find_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> TaskstateResult:
        """Find task by idempotency key.

        Used for dedupe: check if a task already exists for a given note.

        Args:
            idempotency_key: The idempotency key to search for (e.g., "misskey:{note_id}")

        Returns:
            TaskstateResult with task data if found, or success=False if not found
        """
        args = ["task", "list", "--json", json.dumps({"idempotency_key": idempotency_key})]
        result = self._run_cli(args)

        if result.success and result.data:
            tasks = result.data if isinstance(result.data, list) else [result.data]
            if tasks:
                # Return the first (and should be only) matching task
                return TaskstateResult(success=True, data=tasks[0])

        return TaskstateResult(success=False, error="Task not found")

    def update_task(
        self,
        *,
        task_id: str,
        fields: dict[str, Any],
    ) -> TaskstateResult:
        """Update task fields.

        Args:
            task_id: Task ID
            fields: Dictionary of fields to update (e.g., {"reply_state": "sent"})

        Returns:
            TaskstateResult with updated task data
        """
        args = ["task", "update", "--task", task_id]
        for key, value in fields.items():
            args.extend(["--set", f"{key}={value}"])
        return self._run_cli(args)

    def increment_retry_count(
        self,
        *,
        task_id: str,
    ) -> TaskstateResult:
        """Increment retry_count for a task.

        Args:
            task_id: Task ID

        Returns:
            TaskstateResult with updated task data
        """
        # Get current task to read retry_count
        show_result = self._run_cli(["task", "show", "--task", task_id])
        if not show_result.success:
            return show_result

        current_count = show_result.data.get("retry_count", 0) if show_result.data else 0
        new_count = current_count + 1

        return self.update_task(task_id=task_id, fields={"retry_count": new_count})

    def save_kestra_execution_id(
        self,
        *,
        task_id: str,
        execution_id: str,
    ) -> TaskstateResult:
        """Save Kestra execution ID to task.

        Args:
            task_id: Task ID
            execution_id: Kestra execution ID

        Returns:
            TaskstateResult with updated task data
        """
        return self.update_task(
            task_id=task_id,
            fields={"kestra_execution_id": execution_id},
        )