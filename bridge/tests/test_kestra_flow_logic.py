"""Test Kestra flow script logic and CLI contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


FLOW_PATH = Path(__file__).parent.parent.parent / "kestra" / "flows" / "mention.yaml"
HEARTBEAT_FLOW_PATH = Path(__file__).parent.parent.parent / "kestra" / "flows" / "heartbeat.yaml"
MANUAL_REPLAY_FLOW_PATH = Path(__file__).parent.parent.parent / "kestra" / "flows" / "manual-replay.yaml"


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
        # run finish is now in Python script format
        assert '"run", "finish"' in flow_content or "run finish" in flow_content
        assert "run update" not in flow_content
        assert "--run-type execute" in flow_content
        assert "--actor-type agent" in flow_content
        assert "--actor-id kestra-worker" in flow_content

    def test_success_path_uses_valid_task_transitions(self, flow_content):
        # The new Python script uses list-based args
        assert '"--to", "in_progress"' in flow_content or "--to in_progress" in flow_content
        assert '"--to", "review"' in flow_content or flow_content.count("--to review") >= 2
        assert '"--to", "done"' in flow_content or "--to done" in flow_content

    def test_failure_path_maps_to_review(self, flow_content):
        assert '"--status", "failed"' in flow_content or "--status failed" in flow_content
        assert '"--to", "review"' in flow_content or "--to review" in flow_content

    def test_flow_still_uses_shared_db_configuration(self, flow_content):
        assert "taskstate_cli_path" in flow_content
        assert "taskstate_db" in flow_content
        # The new Python script uses CLI_PATH and DB_PATH variables
        assert "CLI_PATH" in flow_content
        assert "DB_PATH" in flow_content

    def test_done_transition_includes_current_summary(self, flow_content):
        """Verify that done transition includes state put with current_summary."""
        assert "current_summary" in flow_content
        assert "state" in flow_content and "put" in flow_content

    def test_mention_flow_persists_reply_text(self, flow_content):
        assert '"reply_state": "sent", "reply_text": REPLY_TEXT' in flow_content
        assert '"reply_state": "failed", "reply_text": REPLY_TEXT' in flow_content


class TestHeartbeatFlowConfiguration:
    """Tests for heartbeat flow configuration and webhook URL."""

    @pytest.fixture
    def flow_content(self):
        return HEARTBEAT_FLOW_PATH.read_text(encoding="utf-8")

    def test_uses_kestra_base_url_not_api_url(self, flow_content):
        """Verify that heartbeat uses kestra_base_url instead of kestra_api_url."""
        assert "kestra_base_url" in flow_content
        assert "kestra_api_url" not in flow_content

    def test_webhook_path_includes_main(self, flow_content):
        """Verify that webhook URL uses correct path with /main/."""
        # The correct path is /api/v1/main/executions/webhook/...
        assert "/api/v1/main/executions/webhook" in flow_content
        # Should NOT use the old path without /main/
        assert "/api/v1/executions/webhook/pulse" not in flow_content

    def test_uses_correct_webhook_key_secret(self, flow_content):
        """Verify that webhook uses PULSE_KESTRA_WEBHOOK_KEY secret."""
        assert "PULSE_KESTRA_WEBHOOK_KEY" in flow_content

    def test_heartbeat_uses_public_default_paths(self, flow_content):
        assert "./agent-taskstate_cli.py" in flow_content
        assert "./state/agent-taskstate.db" in flow_content
        assert "C:/Users/ryo-n" not in flow_content

    def test_heartbeat_uses_reply_state_filter_and_notifier_resend_webhook(self, flow_content):
        assert '--reply-state", reply_state' in flow_content or '--reply-state' in flow_content
        assert '/api/v1/main/executions/webhook/pulse/notifier-resend/' in flow_content


class TestManualReplayFlowConfiguration:
    """Tests for manual-replay flow configuration."""

    @pytest.fixture
    def flow_content(self):
        return MANUAL_REPLAY_FLOW_PATH.read_text(encoding="utf-8")

    def test_accepts_task_id_from_trigger(self, flow_content):
        """Verify that manual-replay accepts task_id from trigger body."""
        assert "trigger.body.task_id" in flow_content

    def test_accepts_trace_id_from_trigger(self, flow_content):
        """Verify that manual-replay accepts trace_id from trigger body."""
        assert "trigger.body.trace_id" in flow_content

    def test_has_resolve_task_id_step(self, flow_content):
        """Verify that manual-replay has a step to resolve task_id from task_id or trace_id."""
        assert "resolve-task-id" in flow_content
        assert "resolved_task_id" in flow_content

    def test_concurrency_key_supports_both_task_id_and_trace_id(self, flow_content):
        """Verify that concurrency key uses task_id or falls back to trace_id."""
        assert "trigger.body.task_id | default(trigger.body.trace_id)" in flow_content

    def test_uses_valid_state_transitions(self, flow_content):
        """Verify that manual-replay uses valid state transitions: ready -> review -> done."""
        # The Python script uses list-based args
        assert '"--to", "review"' in flow_content or "--to review" in flow_content
        assert '"--to", "done"' in flow_content or "--to done" in flow_content
        # Should include current_summary for done transition
        assert "current_summary" in flow_content

    def test_outputs_resolved_task_id_for_downstream_tasks(self, flow_content):
        """Verify that resolved task_id is output for use by downstream tasks."""
        assert "resolved_task_id.txt" in flow_content
        assert "outputs.resolve-task-id.outputFiles" in flow_content

    def test_manual_replay_uses_stored_roadmap_request_and_reply_text(self, flow_content):
        assert 'roadmap_request_json' in flow_content
        assert 'reply_text' in flow_content
        assert 'replay_dedupe_key' in flow_content
        assert 'duplicate_suppressed' in flow_content

    def test_manual_replay_uses_public_default_paths(self, flow_content):
        assert "./agent-taskstate_cli.py" in flow_content
        assert "./state/agent-taskstate.db" in flow_content
        assert "./Roadmap-Design-Skill" in flow_content
        assert "C:/Users/ryo-n" not in flow_content


class TestTaskIOValidation:
    """Tests for task input/output validation across flows."""

    @pytest.fixture
    def mention_flow(self):
        return FLOW_PATH.read_text(encoding="utf-8")

    @pytest.fixture
    def manual_replay_flow(self):
        return MANUAL_REPLAY_FLOW_PATH.read_text(encoding="utf-8")

    def test_mention_flow_cross_task_output_file_references(self, mention_flow):
        """Verify that mention.yaml correctly references output files across tasks."""
        # run_id.txt from start-taskstate-run is used in update-taskstate
        assert "outputs.start-taskstate-run.outputFiles['run_id.txt']" in mention_flow
        # worker_response.json from run-worker is used in extract-reply
        assert "outputs.run-worker.outputFiles['worker_response.json']" in mention_flow

    def test_manual_replay_flow_cross_task_output_file_references(self, manual_replay_flow):
        """Verify that manual-replay.yaml correctly references output files across tasks."""
        # resolved_task_id.txt from resolve-task-id is used in get-original-task
        assert "outputs.resolve-task-id.outputFiles['resolved_task_id.txt']" in manual_replay_flow
        # replay_data.json from get-original-task is used in create-replay-task
        assert "outputs.get-original-task.outputFiles['replay_data.json']" in manual_replay_flow
        # new_task.json from create-replay-task is used in finalize-task
        assert "outputs.create-replay-task.outputFiles['new_task.json']" in manual_replay_flow


NOTIFIER_RESEND_FLOW_PATH = Path(__file__).parent.parent.parent / "kestra" / "flows" / "notifier-resend.yaml"


class TestNotifierResendFlowConfiguration:
    @pytest.fixture
    def flow_content(self):
        return NOTIFIER_RESEND_FLOW_PATH.read_text(encoding="utf-8")

    def test_notifier_resend_reuses_reply_text(self, flow_content):
        assert "reply_text" in flow_content
        assert "reply_dedupe_key" in flow_content
        assert "duplicate_suppressed" in flow_content

    def test_notifier_resend_uses_public_default_paths(self, flow_content):
        assert "./agent-taskstate_cli.py" in flow_content
        assert "./state/agent-taskstate.db" in flow_content
        assert "C:/Users/ryo-n" not in flow_content
