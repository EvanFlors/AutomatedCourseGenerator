from __future__ import annotations

from dataclasses import dataclass, field

from cogenai.application.orchestrator.evaluator import EvaluationIssue
from cogenai.application.orchestrator.refiners.issue_analyzer import IssueAnalysis
from cogenai.application.orchestrator.refiners.base import RefinementLevel


@dataclass(frozen=True)
class Budget:
    max_steps: int = 8
    max_tokens_estimate: int = 8000


@dataclass(frozen=True)
class RefinementStep:
    step_id: int
    level: RefinementLevel
    target_id: str
    issue_ids: tuple[str, ...]
    depends_on: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RefinementPlan:
    steps: tuple[RefinementStep, ...]
    skipped_issue_ids: tuple[str, ...]
    rationale: str = ""


class RefinementPlanner:

    LEVEL_ORDER: tuple[RefinementLevel, ...] = (
        "context",
        "metadata",
        "prerequisites",
        "plan",
        "module",
        "section",
        "block",
    )

    def plan(
        self,
        analysis: IssueAnalysis,
        course_id: str,
        budget: Budget | None = None,
    ) -> RefinementPlan:
        budget = budget or Budget()
        steps: list[RefinementStep] = []
        skipped: list[str] = []
        emitted_issue_ids: set[str] = set()
        step_id = 0
        step_id_by_level: dict[RefinementLevel, int] = {}

        for level in self.LEVEL_ORDER:
            issues = analysis.issues_for(level)
            if not issues:
                continue
            fresh = tuple(i for i in issues if i.id not in emitted_issue_ids)
            if not fresh:
                continue
            target_id = self._target_id_for(level, course_id, fresh)
            if step_id >= budget.max_steps:
                skipped.extend(i.id for i in fresh)
                continue
            step_id += 1
            depends_on: tuple[int, ...] = ()
            for prev_level, prev_step_id in step_id_by_level.items():
                cascade_targets = analysis.cascade.get(prev_level, ())
                if level in cascade_targets:
                    depends_on = depends_on + (prev_step_id,)
            issue_ids = tuple(i.id for i in fresh)
            emitted_issue_ids.update(issue_ids)
            steps.append(
                RefinementStep(
                    step_id=step_id,
                    level=level,
                    target_id=target_id,
                    issue_ids=issue_ids,
                    depends_on=depends_on,
                )
            )
            step_id_by_level[level] = step_id

        rationale = self._build_rationale(steps, skipped)
        return RefinementPlan(
            steps=tuple(steps),
            skipped_issue_ids=tuple(skipped),
            rationale=rationale,
        )

    def _target_id(
        self,
        level: RefinementLevel,
        course_id: str,
        issues: tuple[EvaluationIssue, ...],
    ) -> str:
        for issue in issues:
            if issue.target_id:
                return issue.target_id
        return course_id

    def _target_id_for(
        self,
        level: RefinementLevel,
        course_id: str,
        issues: tuple[EvaluationIssue, ...],
    ) -> str:
        return self._target_id(level, course_id, issues)

    def _build_rationale(
        self,
        steps: list[RefinementStep],
        skipped: list[str],
    ) -> str:
        if not steps:
            return "No refinement steps needed."
        parts = [
            f"{s.level} step #{s.step_id} targeting {s.target_id}"
            f" ({len(s.issue_ids)} issues)"
            for s in steps
        ]
        if skipped:
            parts.append(f"Skipped {len(skipped)} issue(s) due to budget.")
        return "; ".join(parts)
