from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from cogenai.bootstrap.orchestrator import (
    _applied_levels,
    _needs_section_regen,
    _needs_skeleton_regen,
)


@dataclass
class _StubStep:
    level: str


@dataclass
class _StubRefined:
    steps_applied: tuple = ()


def _bundle() -> Any:
    """Lightweight stand-in for CourseBundle; we only check `is not None`."""
    return object()


class TestAppliedLevels:
    def test_returns_empty_for_none(self):
        assert _applied_levels(None) == frozenset()

    def test_returns_empty_for_empty_tuple(self):
        assert _applied_levels(_StubRefined(steps_applied=())) == frozenset()

    def test_collects_distinct_levels(self):
        refined = _StubRefined(steps_applied=(
            _StubStep(level="context"),
            _StubStep(level="metadata"),
            _StubStep(level="context"),
        ))
        assert _applied_levels(refined) == frozenset({"context", "metadata"})

    def test_handles_steps_without_level_attr(self):
        @dataclass
        class _Bad:
            pass
        assert _applied_levels(_StubRefined(steps_applied=(_Bad(),))) == frozenset()


class TestNeedsSectionRegen:
    def test_no_refinement_means_regen(self):
        assert _needs_section_regen(None) is True

    def test_only_metadata_skips_section_regen(self):
        refined = _StubRefined(steps_applied=(_StubStep(level="metadata"),))
        assert _needs_section_regen(refined) is False

    def test_only_context_skips_section_regen(self):
        refined = _StubRefined(steps_applied=(_StubStep(level="context"),))
        assert _needs_section_regen(refined) is False

    def test_metadata_plus_context_skips(self):
        refined = _StubRefined(steps_applied=(
            _StubStep(level="metadata"),
            _StubStep(level="context"),
        ))
        assert _needs_section_regen(refined) is False

    def test_plan_refinement_regens(self):
        refined = _StubRefined(steps_applied=(_StubStep(level="plan"),))
        assert _needs_section_regen(refined) is True

    def test_module_refinement_regens(self):
        refined = _StubRefined(steps_applied=(_StubStep(level="module"),))
        assert _needs_section_regen(refined) is True

    def test_block_refinement_regens(self):
        refined = _StubRefined(steps_applied=(_StubStep(level="block"),))
        assert _needs_section_regen(refined) is True

    def test_mixed_metadata_and_module_regens(self):
        refined = _StubRefined(steps_applied=(
            _StubStep(level="metadata"),
            _StubStep(level="module"),
        ))
        assert _needs_section_regen(refined) is True


class TestNeedsSkeletonRegen:
    def test_no_bundle_means_regen(self):
        assert _needs_skeleton_regen(None, None, None) is True

    def test_bundle_no_issues_passes(self):
        # A passing prior result and only-metadata refinement → reuse
        refined = _StubRefined(steps_applied=(_StubStep(level="metadata"),))
        assert _needs_skeleton_regen(None, _bundle(), refined) is False

    def test_bundle_with_remaining_issues_regens(self):
        @dataclass
        class _Result:
            evaluation_passed: bool = False
        refined = _StubRefined(steps_applied=(_StubStep(level="metadata"),))
        assert _needs_skeleton_regen(_Result(), _bundle(), refined) is True

    def test_context_refinement_regens_skeleton(self):
        # Context affects how planner generates skeleton → must regen
        refined = _StubRefined(steps_applied=(_StubStep(level="context"),))
        assert _needs_skeleton_regen(None, _bundle(), refined) is True

    def test_plan_refinement_regens_skeleton(self):
        refined = _StubRefined(steps_applied=(_StubStep(level="plan"),))
        assert _needs_skeleton_regen(None, _bundle(), refined) is True

    def test_no_refinement_with_bundle_regens(self):
        # First iteration: bundle exists only from prior run; fresh refinement = regen
        assert _needs_skeleton_regen(None, _bundle(), None) is True