"""Test TaskstateGateway."""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from bridge.config import Settings
from bridge.services.taskstate_gateway import TaskstateGateway, TaskstateResult


class TestTaskstateGateway:
    """Tests for TaskstateGateway."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            taskstate_db="/tmp/test.db",
            taskstate_cli_path="",
        )

    @pytest.fixture
    def gateway(self, settings):
        """Create gateway instance."""
        return TaskstateGateway(settings)

    def test_run_cli_success(self, gateway):
        """Test successful CLI execution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"ok": True, "data": {"id": "task123"}})
        mock_result.stderr = ""

        with patch.object(subprocess, "run", return_value=mock_result):
            result = gateway._run_cli(["task", "list"])

        assert result.success
        assert result.data == {"id": "task123"}

    def test_run_cli_failure(self, gateway):
        """Test failed CLI execution."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: something went wrong"

        with patch.object(subprocess, "run", return_value=mock_result):
            result = gateway._run_cli(["task", "create"])

        assert not result.success
        assert "something went wrong" in result.error

    def test_run_cli_timeout(self, gateway):
        """Test CLI timeout."""
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd="test", timeout=30)):
            result = gateway._run_cli(["task", "list"])

        assert not result.success
        assert "timed out" in result.error

    def test_run_cli_not_found(self, gateway):
        """Test CLI not found."""
        with patch.object(subprocess, "run", side_effect=FileNotFoundError()):
            result = gateway._run_cli(["task", "list"])

        assert not result.success
        assert "not found" in result.error

    def test_create_task(self, gateway):
        """Test create_task method."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ok": True,
            "data": {"id": "task123", "title": "Test Task"},
        })
        mock_result.stderr = ""

        with patch.object(subprocess, "run", return_value=mock_result) as mock_run:
            result = gateway.create_task(
                title="Test Task",
                goal="Test goal",
            )

        assert result.success
        assert result.data["id"] == "task123"

        # Verify the CLI was called with correct arguments
        call_args = mock_run.call_args[0][0]
        assert "task" in call_args
        assert "create" in call_args

    def test_put_state(self, gateway):
        """Test put_state method."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ok": True,
            "data": {"current_step": "Test step"},
        })
        mock_result.stderr = ""

        with patch.object(subprocess, "run", return_value=mock_result) as mock_run:
            result = gateway.put_state(
                task_id="task123",
                current_step="Test step",
            )

        assert result.success

        # Verify the CLI was called with correct arguments
        call_args = mock_run.call_args[0][0]
        assert "state" in call_args
        assert "put" in call_args
        assert "task123" in call_args

    def test_set_status(self, gateway):
        """Test set_status method."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ok": True,
            "data": {"id": "task123", "status": "ready"},
        })
        mock_result.stderr = ""

        with patch.object(subprocess, "run", return_value=mock_result) as mock_run:
            result = gateway.set_status(
                task_id="task123",
                status="ready",
            )

        assert result.success

        # Verify the CLI was called with correct arguments
        call_args = mock_run.call_args[0][0]
        assert "task" in call_args
        assert "set-status" in call_args
        assert "task123" in call_args
        assert "ready" in call_args

    def test_create_task_for_mention(self, gateway):
        """Test create_task_for_mention convenience method."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ok": True,
            "data": {"id": "task123"},
        })
        mock_result.stderr = ""

        with patch.object(subprocess, "run", return_value=mock_result):
            result = gateway.create_task_for_mention(
                trace_id="trace123",
                note_id="note123",
                username="testuser",
                command="roadmap",
            )

        assert result.success
        assert result.data["id"] == "task123"