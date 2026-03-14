"""Test status mapping."""

import pytest
from bridge.status_mapping import (
    LogicalStatus,
    RunStatus,
    TaskstateStatus,
    logical_to_taskstate,
    taskstate_to_logical,
)


class TestStatusMapping:
    """Tests for status mapping functions."""

    def test_queued_maps_to_ready(self):
        """Test that queued maps to ready."""
        result = logical_to_taskstate(LogicalStatus.QUEUED)
        assert result["task_status"] == TaskstateStatus.READY
        assert result["run_status"] is None

    def test_running_maps_to_in_progress_and_running(self):
        """Test that running maps to in_progress + run.running."""
        result = logical_to_taskstate(LogicalStatus.RUNNING)
        assert result["task_status"] == TaskstateStatus.IN_PROGRESS
        assert result["run_status"] == RunStatus.RUNNING

    def test_waiting_maps_to_blocked(self):
        """Test that waiting maps to blocked."""
        result = logical_to_taskstate(LogicalStatus.WAITING)
        assert result["task_status"] == TaskstateStatus.BLOCKED
        assert result["run_status"] is None

    def test_needs_review_maps_to_review(self):
        """Test that needs_review maps to review."""
        result = logical_to_taskstate(LogicalStatus.NEEDS_REVIEW)
        assert result["task_status"] == TaskstateStatus.REVIEW
        assert result["run_status"] is None

    def test_done_maps_to_done_and_succeeded(self):
        """Test that done maps to done + run.succeeded."""
        result = logical_to_taskstate(LogicalStatus.DONE)
        assert result["task_status"] == TaskstateStatus.DONE
        assert result["run_status"] == RunStatus.SUCCEEDED

    def test_failed_maps_to_review_and_failed(self):
        """Test that failed maps to review + run.failed."""
        result = logical_to_taskstate(LogicalStatus.FAILED)
        assert result["task_status"] == TaskstateStatus.REVIEW
        assert result["run_status"] == RunStatus.FAILED

    def test_cancelled_maps_to_archived_and_cancelled(self):
        """Test that cancelled maps to archived + run.cancelled."""
        result = logical_to_taskstate(LogicalStatus.CANCELLED)
        assert result["task_status"] == TaskstateStatus.ARCHIVED
        assert result["run_status"] == RunStatus.CANCELLED

    def test_taskstate_to_logical_queued(self):
        """Test taskstate ready to logical queued."""
        result = taskstate_to_logical("ready")
        assert result == LogicalStatus.QUEUED

    def test_taskstate_to_logical_waiting(self):
        """Test taskstate blocked to logical waiting."""
        result = taskstate_to_logical("blocked")
        assert result == LogicalStatus.WAITING

    def test_taskstate_to_logical_running(self):
        """Test taskstate in_progress + running to logical running."""
        result = taskstate_to_logical("in_progress", "running")
        assert result == LogicalStatus.RUNNING

    def test_taskstate_to_logical_done(self):
        """Test taskstate done + succeeded to logical done."""
        result = taskstate_to_logical("done", "succeeded")
        assert result == LogicalStatus.DONE

    def test_taskstate_to_logical_failed(self):
        """Test taskstate review + failed to logical failed."""
        result = taskstate_to_logical("review", "failed")
        assert result == LogicalStatus.FAILED

    def test_taskstate_to_logical_needs_review(self):
        """Test taskstate review (no run) to logical needs_review."""
        result = taskstate_to_logical("review")
        assert result == LogicalStatus.NEEDS_REVIEW

    def test_taskstate_to_logical_cancelled(self):
        """Test taskstate archived + cancelled to logical cancelled."""
        result = taskstate_to_logical("archived", "cancelled")
        assert result == LogicalStatus.CANCELLED


class TestLogicalStatusEnum:
    """Tests for LogicalStatus enum."""

    def test_all_statuses_defined(self):
        """Test that all required statuses are defined."""
        expected = {"queued", "running", "waiting", "needs_review", "done", "failed", "cancelled"}
        actual = {s.value for s in LogicalStatus}
        assert actual == expected


class TestTaskstateStatusEnum:
    """Tests for TaskstateStatus enum."""

    def test_all_statuses_defined(self):
        """Test that all required statuses are defined."""
        expected = {"draft", "ready", "in_progress", "blocked", "review", "done", "archived"}
        actual = {s.value for s in TaskstateStatus}
        assert actual == expected


class TestRunStatusEnum:
    """Tests for RunStatus enum."""

    def test_all_statuses_defined(self):
        """Test that all required statuses are defined."""
        expected = {"running", "succeeded", "failed", "cancelled"}
        actual = {s.value for s in RunStatus}
        assert actual == expected