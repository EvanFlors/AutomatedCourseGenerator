from __future__ import annotations

import pytest

from cogenai.agents_implementations.refiners.issue_analyzer import IssueAnalyzer
from cogenai.agents_implementations.refiners.refinement_planner import (
    Budget,
    RefinementPlanner,
)

from ._fixtures import make_issues


def _analyze(specs):
    analyzer = IssueAnalyzer()
    return analyzer.analyze(make_issues(*specs))


class TestRefinementPlanner:

    def setup_method(self):
        self.planner = RefinementPlanner()

    def test_five_issues_produce_four_steps(self):
        analysis = _analyze(
            (
                ("i-1", "course", "c-1", "audience_alignment"),
                ("i-2", "module", "m-1", "structural"),
                ("i-3", "section", "s-1", "pedagogical"),
                ("i-4", "block", "b-1", "completeness"),
                ("i-5", "block", "b-2", "factual"),
            )
        )
        plan = self.planner.plan(analysis, course_id="c-1")
        assert len(plan.steps) == 4
        levels = [s.level for s in plan.steps]
        assert levels == ["context", "module", "section", "block"]

    def test_steps_have_correct_depends_on_for_cascade(self):
        analysis = _analyze(
            (
                ("i-1", "course", "c-1", "audience_alignment"),
                ("i-2", "module", "m-1", "structural"),
            )
        )
        plan = self.planner.plan(analysis, course_id="c-1")
        context_step = plan.steps[0]
        module_step = plan.steps[1]
        assert context_step.step_id == 1
        assert module_step.step_id == 2
        assert module_step.depends_on == (1,)

    def test_block_level_step_has_no_dependency(self):
        analysis = _analyze(
            (("i-1", "block", "b-1", "completeness"),)
        )
        plan = self.planner.plan(analysis, course_id="c-1")
        assert len(plan.steps) == 1
        assert plan.steps[0].depends_on == ()

    def test_target_id_from_issue(self):
        analysis = _analyze(
            (("i-1", "block", "specific-block-id", "completeness"),)
        )
        plan = self.planner.plan(analysis, course_id="fallback-id")
        assert plan.steps[0].target_id == "specific-block-id"

    def test_target_id_falls_back_to_course_id(self):
        analysis = _analyze(
            (("i-1", "course", "", "structural"),)
        )
        plan = self.planner.plan(analysis, course_id="course-fallback")
        assert plan.steps[0].target_id == "course-fallback"

    def test_budget_overflow_marks_skipped(self):
        analysis = _analyze(
            (
                ("i-1", "course", "c-1", "audience_alignment"),
                ("i-2", "module", "m-1", "structural"),
                ("i-3", "section", "s-1", "pedagogical"),
                ("i-4", "block", "b-1", "completeness"),
            )
        )
        plan = self.planner.plan(analysis, course_id="c-1", budget=Budget(max_steps=2))
        assert len(plan.steps) == 2
        assert len(plan.skipped_issue_ids) == 2
        assert "i-3" in plan.skipped_issue_ids
        assert "i-4" in plan.skipped_issue_ids

    def test_always_includes_failing_issue_repeated_iteration(self):
        analysis = _analyze(
            (("i-1", "block", "b-1", "completeness"),)
        )
        plan_first = self.planner.plan(analysis, course_id="c-1")
        plan_second = self.planner.plan(analysis, course_id="c-1")
        assert len(plan_first.steps) == 1
        assert len(plan_second.steps) == 1
        assert plan_first.steps[0].target_id == plan_second.steps[0].target_id

    def test_step_ids_are_sequential(self):
        analysis = _analyze(
            (
                ("i-1", "course", "c-1", "audience_alignment"),
                ("i-2", "module", "m-1", "structural"),
                ("i-3", "section", "s-1", "pedagogical"),
            )
        )
        plan = self.planner.plan(analysis, course_id="c-1")
        ids = [s.step_id for s in plan.steps]
        assert ids == list(range(1, len(plan.steps) + 1))

    def test_rationale_includes_steps(self):
        analysis = _analyze(
            (("i-1", "block", "b-1", "completeness"),)
        )
        plan = self.planner.plan(analysis, course_id="c-1")
        assert "block" in plan.rationale

    def test_empty_issues_returns_empty_plan(self):
        analysis = _analyze(())
        plan = self.planner.plan(analysis, course_id="c-1")
        assert plan.steps == ()
        assert plan.skipped_issue_ids == ()
        assert "No refinement" in plan.rationale
