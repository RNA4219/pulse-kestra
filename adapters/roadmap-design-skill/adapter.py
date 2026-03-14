"""Adapter for Roadmap Design Skill.

Transforms pulse-kestra RoadmapRequest to Roadmap Design Skill RoadmapRequest.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4


def transform_roadmap_request(
    simple_request: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    """Transform simple RoadmapRequest to Roadmap Design Skill format.

    Args:
        simple_request: Simple request with goal, context, constraints, deadline
        trace_id: Trace ID for correlation

    Returns:
        Roadmap Design Skill compatible request
    """
    goal = simple_request.get("goal", "")
    context = simple_request.get("context")
    constraints = simple_request.get("constraints", [])
    deadline = simple_request.get("deadline")

    # Generate IDs
    problem_id = f"pb_{uuid4().hex[:12]}"
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    # Build problem statement
    problem_statement = {
        "problem_id": problem_id,
        "title": goal[:100] if len(goal) > 100 else goal,
        "statement": goal,
        "background": context,
        "desired_outcome": f"Complete by {deadline}" if deadline else None,
    }

    # Build constraints
    constraint_items = []
    for i, c in enumerate(constraints):
        constraint_items.append({
            "constraint_id": f"co_{timestamp}_{i:03d}",
            "category": "other",
            "statement": c,
            "severity": "soft",
        })

    # Add deadline as hard constraint if specified
    if deadline:
        constraint_items.append({
            "constraint_id": f"co_{timestamp}_deadline",
            "category": "time",
            "statement": f"Must be completed by {deadline}",
            "severity": "hard",
        })

    # Build minimal insights (derived from goal)
    insights = [{
        "insight_id": f"in_{timestamp}_001",
        "statement": f"Goal: {goal}",
        "source": "user_request",
        "importance": "high",
    }]

    # Build minimal available assets
    available_assets = [{
        "asset_id": f"as_{timestamp}_001",
        "type": "skill",
        "name": "Roadmap Design Skill",
        "description": "AI-powered roadmap planning capability",
    }]

    return {
        "schema_version": "1.0.0",
        "mode": "roadmap",
        "problem_statement": problem_statement,
        "insights": insights,
        "constraints": constraint_items if constraint_items else [
            {
                "constraint_id": f"co_{timestamp}_default",
                "category": "other",
                "statement": "No specific constraints provided",
                "severity": "soft",
            }
        ],
        "available_assets": available_assets,
        "run_id": trace_id,
        "response_language": None,
        "known_failures": None,
        "evidence_refs": None,
        "notes": [context] if context else None,
        "priority_hint": "medium",
        "assumptions": None,
    }


def extract_reply_text(response: dict[str, Any]) -> str:
    """Extract reply text from Roadmap Design Skill response.

    Args:
        response: Response from Roadmap Design Skill

    Returns:
        Human-readable summary for Misskey reply
    """
    if not response:
        return "ロードマップの生成に失敗しました。"

    run_status = response.get("run", {}).get("status", "")
    if run_status != "completed":
        error_msg = response.get("run", {}).get("message", "Unknown error")
        return f"ロードマップ生成中にエラーが発生しました: {error_msg}"

    roadmap = response.get("roadmap", {})
    phases = roadmap.get("phases", [])

    if not phases:
        return "ロードマップが生成されましたが、フェーズが含まれていません。"

    # Build summary
    lines = ["ロードマップを生成しました！\n"]

    for i, phase in enumerate(phases[:5], 1):  # Limit to 5 phases
        phase_title = phase.get("title", f"フェーズ {i}")
        phase_summary = phase.get("summary", "")
        lines.append(f"**{i}. {phase_title}**")
        if phase_summary:
            lines.append(f"  {phase_summary[:100]}")

    if len(phases) > 5:
        lines.append(f"\n...他 {len(phases) - 5} フェーズ")

    # Add link to full roadmap if available
    lines.append("\n詳細なロードマップは別途ご確認ください。")

    return "\n".join(lines)