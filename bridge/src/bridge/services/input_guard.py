"""Input guard service for lightweight safety checks.

Implements FR-010, FR-011, FR-012 from requirements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class GuardDecision(str, Enum):
    """Guard decision result.

    - PASS: Input is safe, continue processing
    - REJECT: Input is dangerous, reject immediately
    - NEEDS_REVIEW: Input is suspicious, require human review
    - LOG_ONLY: Input has minor issues, log but continue
    """

    PASS = "pass"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"
    LOG_ONLY = "log_only"


@dataclass
class GuardResult:
    """Result of input guard check.

    Attributes:
        decision: The guard decision
        reason: Human-readable reason for the decision
        matched_patterns: List of patterns that matched
        metadata: Additional metadata for logging
    """

    decision: GuardDecision
    reason: str = ""
    matched_patterns: list[str] | None = None
    metadata: dict[str, Any] | None = None

    @property
    def is_pass(self) -> bool:
        """Check if the input passed the guard."""
        return self.decision == GuardDecision.PASS

    @property
    def is_reject(self) -> bool:
        """Check if the input was rejected."""
        return self.decision == GuardDecision.REJECT

    @property
    def needs_review(self) -> bool:
        """Check if the input needs human review."""
        return self.decision == GuardDecision.NEEDS_REVIEW


class InputGuard:
    """Lightweight input guard for safety checks.

    Phase 1 implementation focuses on:
    - Basic pattern matching for obvious threats
    - Configurable thresholds
    - No heavy ML/parsing
    """

    # Patterns that always reject
    REJECT_PATTERNS = [
        # Prompt injection attempts
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
        re.compile(r"ignore\s+(all\s+)?prompts?", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(previous\s+)?instructions?", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
        re.compile(r"<\s*system\s*>", re.IGNORECASE),
        re.compile(r"\[system\]", re.IGNORECASE),
        # Obviously malicious
        re.compile(r"sudo\s+rm\s+-rf", re.IGNORECASE),
        re.compile(r"format\s+c:", re.IGNORECASE),
        re.compile(r"rm\s+-rf\s+/", re.IGNORECASE),
    ]

    # Patterns that trigger review
    REVIEW_PATTERNS = [
        # Potentially sensitive operations
        re.compile(r"delete\s+(all|everything)", re.IGNORECASE),
        re.compile(r"remove\s+(all|everything)", re.IGNORECASE),
        re.compile(r"drop\s+table", re.IGNORECASE),
        re.compile(r"truncate\s+table", re.IGNORECASE),
        # Role-play attempts
        re.compile(r"(act|pretend|play)\s+as\s+(if\s+you\s+are|a)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(a|an)\s+\w+", re.IGNORECASE),
    ]

    # Patterns that are logged but not blocked
    LOG_PATTERNS = [
        # Long input (potential resource exhaustion)
        # Checked separately by length
        # Repeated characters
        re.compile(r"(.)\1{20,}"),
        # Excessive caps
        re.compile(r"[A-Z]{50,}"),
    ]

    def __init__(
        self,
        max_length: int = 10000,
        enable_reject: bool = True,
        enable_review: bool = True,
        enable_log: bool = True,
    ):
        """Initialize input guard.

        Args:
            max_length: Maximum allowed input length
            enable_reject: Enable reject-level checks
            enable_review: Enable review-level checks
            enable_log: Enable log-level checks
        """
        self.max_length = max_length
        self.enable_reject = enable_reject
        self.enable_review = enable_review
        self.enable_log = enable_log

    def check(self, text: str) -> GuardResult:
        """Check input text against guard rules.

        Args:
            text: Input text to check

        Returns:
            GuardResult with decision and details
        """
        if not text:
            return GuardResult(decision=GuardDecision.PASS)

        matched_patterns: list[str] = []

        # Check length
        if len(text) > self.max_length:
            return GuardResult(
                decision=GuardDecision.REJECT,
                reason=f"Input exceeds maximum length ({len(text)} > {self.max_length})",
                metadata={"length": len(text), "max_length": self.max_length},
            )

        # Check reject patterns
        if self.enable_reject:
            for pattern in self.REJECT_PATTERNS:
                if pattern.search(text):
                    matched_patterns.append(pattern.pattern)
                    return GuardResult(
                        decision=GuardDecision.REJECT,
                        reason="Input contains potentially malicious content",
                        matched_patterns=matched_patterns,
                        metadata={"pattern_type": "reject"},
                    )

        # Check review patterns
        if self.enable_review:
            for pattern in self.REVIEW_PATTERNS:
                if pattern.search(text):
                    matched_patterns.append(pattern.pattern)
                    return GuardResult(
                        decision=GuardDecision.NEEDS_REVIEW,
                        reason="Input requires human review",
                        matched_patterns=matched_patterns,
                        metadata={"pattern_type": "review"},
                    )

        # Check log patterns
        if self.enable_log:
            for pattern in self.LOG_PATTERNS:
                if pattern.search(text):
                    matched_patterns.append(pattern.pattern)
                    # Continue processing but log
                    return GuardResult(
                        decision=GuardDecision.LOG_ONLY,
                        reason="Input has unusual patterns",
                        matched_patterns=matched_patterns,
                        metadata={"pattern_type": "log"},
                    )

        # All checks passed
        return GuardResult(decision=GuardDecision.PASS)

    def check_json_payload(self, payload: dict[str, Any]) -> GuardResult:
        """Check JSON payload for guard rules.

        Checks the 'text' field and any nested content.

        Args:
            payload: JSON payload to check

        Returns:
            GuardResult with decision
        """
        # Extract text fields to check
        texts_to_check: list[str] = []

        def extract_texts(obj: Any, depth: int = 0) -> None:
            if depth > 5:  # Limit recursion depth
                return
            if isinstance(obj, str):
                texts_to_check.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    extract_texts(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    extract_texts(item, depth + 1)

        extract_texts(payload)

        # Check each text
        for text in texts_to_check:
            result = self.check(text)
            if not result.is_pass:
                return result

        return GuardResult(decision=GuardDecision.PASS)