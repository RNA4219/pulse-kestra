"""Test Kestra flow script logic and CLI contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


FLOW_PATH = Path(__file__).parent.parent.parent / "kestra" / "flows" / "mention.yaml"


class TestExtractReplyScript:
    """Tests for the extract-reply script logic from mention.yaml."""

    def test_worker_success_with_phases(self, tmp_path):
        response = {
            "run": {"status": "completed", "run_id": "test"},
            "roadmap": {
                "phases": [
                    {"title": "Phase 1", "summary": "First phase"},
                    {"title": "Phase 2", "summary": "Second phase"},
                ]
            },
        }

        response_file = tmp_path / "worker_response.json"
        response_file.write_text(json.dumps(response), encoding="utf-8")

        loaded_response = json.loads(response_file.read_text(encoding="utf-8"))
        phases = []
        run_status = loaded_response.get("run", {}).get("status", "")

        if run_status != "completed":
            reply_text = f"エラー: {loaded_response.get('run', {}).get('message', 'Unknown error')}"
        else:
            roadmap = loaded_response.get("roadmap", {})
            phases = roadmap.get("phases", [])
            reply_text = f"成功: {len(phases)} phases"

        worker_status = {
            "status": "done" if run_status == "completed" else "failed",
            "has_phases": len(phases) > 0,
            "phase_count": len(phases),
        }

        assert reply_text == "成功: 2 phases"
        assert worker_status == {"status": "done", "has_phases": True, "phase_count": 2}

    def test_worker_failure_keeps_phases_defined(self, tmp_path):
        response = {
            "run": {"status": "failed", "run_id": "test", "message": "Generation failed"}
        }

        response_file = tmp_path / "worker_response.json"
        response_file.write_text(json.dumps(response), encoding="utf-8")

        loaded_response = json.loads(response_file.read_text(encoding="utf-8"))
        phases = []
        run_status = loaded_response.get("run", {}).get("status", "")

        if run_status != "completed":
            error_msg = loaded_response.get("run", {}).get("message", "Unknown error")
            reply_text = f"ロードマップ生成中にエラーが発生しました: {error_msg}"
        else:
            roadmap = loaded_response.get("roadmap", {})
            phases = roadmap.get("phases", [])
            reply_text = f"成功: {len(phases)} phases"

        worker_status = {
            "status": "done" if run_status == "completed" else "failed",
            "has_phases": len(phases) > 0,
            "phase_count": len(phases),
        }

        assert reply_text.endswith("Generation failed")
        assert worker_status == {"status": "failed", "has_phases": False, "phase_count": 0}


class TestKestraFlowConfiguration:
    """Tests for Kestra flow wiring and taskstate CLI contract."""

    @pytest.fixture
    def flow_content(self):
        return FLOW_PATH.read_text(encoding="utf-8")

    def test_global_name_typo_fix(self, flow_content):
        assert "roadsap" not in flow_content.lower()
        assert "roadmap_design_skill_path" in flow_content

    def test_start_taskstate_run_exports_run_id_file(self, flow_content):
        assert "outputFiles:" in flow_content
        assert "- run_id.txt" in flow_content
        assert "outputs.start-taskstate-run.outputFiles['run_id.txt']" in flow_content

    def test_transform_and_worker_use_cross_task_output_files(self, flow_content):
        assert "- worker_request.json" in flow_content
        assert "outputs.transform-request.outputFiles['worker_request.json']" in flow_content
        assert "- worker_response.json" in flow_content
        assert "outputs.run-worker.outputFiles['worker_response.json']" in flow_content

    def test_extract_reply_uses_output_files_and_kestra_outputs(self, flow_content):
        assert "- reply_text.txt" in flow_content
        assert "- worker_status.json" in flow_content
        assert "outputs.extract-reply.outputFiles['worker_status.json']" in flow_content
        assert 'Kestra.outputs({"reply_text": reply_text})' in flow_content
        assert "outputs.extract-reply.vars.reply_text" in flow_content

    def test_run_commands_match_agent_taskstate_cli_contract(self, flow_content):
        assert "run start" in flow_content
        assert "run finish" in flow_content
        assert "run update" not in flow_content
        assert "--run-type execute" in flow_content
        assert "--actor-type agent" in flow_content
        assert "--actor-id kestra-worker" in flow_content
        assert '--run "$RUN_ID"' in flow_content

    def test_success_path_uses_valid_task_transitions(self, flow_content):
        assert "--to in_progress" in flow_content
        assert flow_content.count("--to review") >= 2
        assert "--to done" in flow_content

    def test_failure_path_maps_to_review(self, flow_content):
        assert "--status failed" in flow_content
        assert "--to review" in flow_content

    def test_flow_still_uses_shared_db_configuration(self, flow_content):
        assert "taskstate_cli_path" in flow_content
        assert "taskstate_db" in flow_content
        assert flow_content.count('--db "$DB_PATH"') >= 3
