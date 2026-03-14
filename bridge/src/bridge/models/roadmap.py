"""RoadmapRequest model for @pulse roadmap command."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RoadmapRequest(BaseModel):
    """Request payload for roadmap design skill.

    This is the expected JSON structure inside the first ```json code block
    in a @pulse roadmap mention.
    """

    goal: str = Field(..., description="The goal or objective to design a roadmap for")
    context: Optional[str] = Field(None, description="Additional context for the roadmap")
    constraints: Optional[list[str]] = Field(
        default_factory=list,
        description="Constraints to consider (time, resources, etc.)"
    )
    deadline: Optional[str] = Field(None, description="Target deadline if any")

    @field_validator("goal")
    @classmethod
    def goal_must_not_be_empty(cls, v: str) -> str:
        """Validate that goal is not empty."""
        if not v or not v.strip():
            raise ValueError("goal must not be empty")
        return v.strip()