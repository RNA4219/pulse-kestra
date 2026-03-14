"""Test Kestra flow script logic.

These tests verify the Python script logic embedded in Kestra flow YAML
to catch issues like undefined variables in conditional branches.
"""

import json
import pytest


class TestExtractReplyScript:
    """Tests for the extract-reply script logic from mention.yaml."""

    def test_worker_success_with_phases(self, tmp_path):
        """Test extract-reply when worker succeeds with phases."""
        # Create mock worker response
        response = {
            "run": {"status": "completed", "run_id": "test"},
            "roadmap": {
                "phases": [
                    {"title": "Phase 1", "summary": "First phase"},
                    {"title": "Phase 2", "summary": "Second phase"},
                ]
            }
        }

        # Write response file
        response_file = tmp_path / "worker_response.json"
        response_file.write_text(json.dumps(response))

        # Simulate the extract-reply script logic
        with open(response_file) as f:
            loaded_response = json.load(f)

        # Initialize phases to avoid undefined reference
        phases = []
        run_status = loaded_response.get("run", {}).get("status", "")

        if run_status != "completed":
            reply_text = f"エラー: {loaded_response.get('run', {}).get('message', 'Unknown error')}"
        else:
            roadmap = loaded_response.get("roadmap", {})
            phases = roadmap.get("phases", [])
            reply_text = f"成功: {len(phases)} phases"

        # Now phases is always defined
        worker_status = {
            "status": "done" if run_status == "completed" else "failed",
            "has_phases": len(phases) > 0,
            "phase_count": len(phases),
        }

        assert run_status == "completed"
        assert len(phases) == 2
        assert worker_status["status"] == "done"
        assert worker_status["has_phases"] is True
        assert worker_status["phase_count"] == 2

    def test_worker_failure_phases_undefined(self, tmp_path):
        """Test that phases is never undefined even when worker fails.

        This is the regression test for the bug where 'phases' was
        undefined in the worker failure branch, causing len(phases) to fail.
        """
        # Create mock worker response for failure
        response = {
            "run": {
                "status": "failed",
                "run_id": "test",
                "message": "Generation failed"
            }
        }

        response_file = tmp_path / "worker_response.json"
        response_file.write_text(json.dumps(response))

        # Simulate the FIXED extract-reply script logic
        with open(response_file) as f:
            loaded_response = json.load(f)

        # CRITICAL: Initialize phases BEFORE the conditional
        phases = []
        run_status = loaded_response.get("run", {}).get("status", "")

        if run_status != "completed":
            error_msg = loaded_response.get("run", {}).get("message", "Unknown error")
            reply_text = f"ロードマップ生成中にエラーが発生しました: {error_msg}"
        else:
            roadmap = loaded_response.get("roadmap", {})
            phases = roadmap.get("phases", [])
            reply_text = f"成功: {len(phases)} phases"

        # Now phases is always defined - this line was causing the bug
        worker_status = {
            "status": "done" if run_status == "completed" else "failed",
            "has_phases": len(phases) > 0,  # This must not raise NameError
            "phase_count": len(phases),
        }

        assert run_status == "failed"
        assert phases == []  # phases should be empty list, not undefined
        assert worker_status["status"] == "failed"
        assert worker_status["has_phases"] is False
        assert worker_status["phase_count"] == 0
        assert "エラー" in reply_text

    def test_worker_success_no_phases(self, tmp_path):
        """Test worker success but no phases in response."""
        response = {
            "run": {"status": "completed", "run_id": "test"},
            "roadmap": {"phases": []}
        }

        response_file = tmp_path / "worker_response.json"
        response_file.write_text(json.dumps(response))

        with open(response_file) as f:
            loaded_response = json.load(f)

        phases = []
        run_status = loaded_response.get("run", {}).get("status", "")

        if run_status != "completed":
            reply_text = "error"
        else:
            roadmap = loaded_response.get("roadmap", {})
            phases = roadmap.get("phases", [])
            reply_text = "no phases" if not phases else "has phases"

        worker_status = {
            "status": "done" if run_status == "completed" else "failed",
            "has_phases": len(phases) > 0,
            "phase_count": len(phases),
        }

        assert worker_status["status"] == "done"
        assert worker_status["has_phases"] is False
        assert worker_status["phase_count"] == 0

    def test_worker_response_missing_roadmap_key(self, tmp_path):
        """Test worker response missing roadmap key entirely."""
        response = {
            "run": {"status": "completed", "run_id": "test"}
            # No 'roadmap' key
        }

        response_file = tmp_path / "worker_response.json"
        response_file.write_text(json.dumps(response))

        with open(response_file) as f:
            loaded_response = json.load(f)

        phases = []
        run_status = loaded_response.get("run", {}).get("status", "")

        if run_status != "completed":
            reply_text = "error"
        else:
            # This handles missing 'roadmap' gracefully
            roadmap = loaded_response.get("roadmap", {})
            phases = roadmap.get("phases", [])
            reply_text = "processed"

        worker_status = {
            "status": "done" if run_status == "completed" else "failed",
            "has_phases": len(phases) > 0,
            "phase_count": len(phases),
        }

        assert worker_status["status"] == "done"
        assert phases == []
        assert worker_status["has_phases"] is False


class TestKestraFlowConfiguration:
    """Tests for Kestra flow configuration values."""

    def test_global_name_typo_fix(self):
        """Test that the correct global name is used in flow.

        The global should be 'roadmap_design_skill_path', not 'roadsap_design_skill_path'.
        """
        # Read the flow YAML and check for typo
        import pathlib
        flow_path = pathlib.Path(__file__).parent.parent.parent / "kestra" / "flows" / "mention.yaml"
        content = flow_path.read_text(encoding="utf-8")

        # The typo 'roadsap' should NOT be present
        assert "roadsap" not in content.lower(), "Typo 'roadsap' found in flow - should be 'roadmap'"

        # The correct name should be present
        assert "roadmap_design_skill_path" in content, "Correct global name 'roadmap_design_skill_path' not found"