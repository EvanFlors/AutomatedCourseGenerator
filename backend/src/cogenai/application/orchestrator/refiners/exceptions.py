from __future__ import annotations

from cogenai.agents_implementations.refiners.base import RefinementLevel


class RefinerError(Exception):
    """Base for all refiner-level errors."""


class RefinerOutputTruncated(RefinerError):
    """LLM hit max_output_tokens before producing valid JSON."""

    def __init__(
        self,
        level: RefinementLevel,
        raw_response_preview: str,
        estimated_tokens: int,
    ):
        self.level = level
        self.raw_response_preview = raw_response_preview
        self.estimated_tokens = estimated_tokens
        super().__init__(
            f"Refiner at level={level} produced truncated output "
            f"(~{estimated_tokens} tokens). Preview: {raw_response_preview[:80]!r}"
        )


class RefinerSchemaMismatch(RefinerError):
    """JSON parsed but missing required fields."""

    def __init__(
        self,
        level: RefinementLevel,
        missing_fields: tuple[str, ...],
    ):
        self.level = level
        self.missing_fields = missing_fields
        super().__init__(
            f"Refiner at level={level} JSON missing fields: {missing_fields}"
        )


class RefinerIdMismatch(RefinerError):
    """LLM returned a different id than the input (D-R11 violation)."""

    def __init__(
        self,
        level: RefinementLevel,
        expected_id: str,
        actual_id: str,
    ):
        self.level = level
        self.expected_id = expected_id
        self.actual_id = actual_id
        super().__init__(
            f"Refiner at level={level} violated id immutability: "
            f"expected={expected_id}, got={actual_id}"
        )
