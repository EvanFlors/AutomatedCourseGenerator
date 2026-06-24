from __future__ import annotations

from dataclasses import dataclass, field

from cogenai.agents_implementations.evaluator import EvaluationIssue
from cogenai.agents_implementations.refiners.base import RefinementLevel


@dataclass(frozen=True)
class IssueAnalysis:
    by_level: dict[RefinementLevel, tuple[EvaluationIssue, ...]] = field(default_factory=dict)
    cascade: dict[RefinementLevel, tuple[RefinementLevel, ...]] = field(default_factory=dict)

    def issues_for(self, level: RefinementLevel) -> tuple[EvaluationIssue, ...]:
        return self.by_level.get(level, ())


class IssueAnalyzer:

    LEVEL_FOR_SCOPE = {
        "course": "context",
        "module": "module",
        "section": "section",
        "block": "block",
    }

    CATEGORY_TO_LEVEL = {
        "audience_alignment": "context",
        "depth": "context",
        "prerequisite": "prerequisites",
        "structural": "plan",
        "metadata": "metadata",
    }

    def analyze(
        self,
        issues: tuple[EvaluationIssue, ...],
    ) -> IssueAnalysis:
        by_level: dict[RefinementLevel, list[EvaluationIssue]] = {
            "context": [],
            "metadata": [],
            "prerequisites": [],
            "plan": [],
            "module": [],
            "section": [],
            "block": [],
        }
        for issue in issues:
            level = self._route(issue)
            by_level[level].append(issue)
        cascade = self._compute_cascade(by_level)
        return IssueAnalysis(
            by_level={k: tuple(v) for k, v in by_level.items()},
            cascade=cascade,
        )

    def _route(self, issue: EvaluationIssue) -> RefinementLevel:
        scope = (issue.scope or "course").lower()
        if scope != "course":
            return self.LEVEL_FOR_SCOPE.get(scope, "context")
        if issue.category in self.CATEGORY_TO_LEVEL:
            return self.CATEGORY_TO_LEVEL[issue.category]
        return "context"

    def _compute_cascade(
        self,
        by_level: dict[RefinementLevel, list[EvaluationIssue]],
    ) -> dict[RefinementLevel, tuple[RefinementLevel, ...]]:
        cascade: dict[RefinementLevel, list[RefinementLevel]] = {}
        if by_level["context"]:
            cascade["context"] = ("metadata", "prerequisites", "plan", "module", "section", "block")
        if by_level["metadata"]:
            cascade["metadata"] = ()
        if by_level["prerequisites"]:
            cascade["prerequisites"] = ("plan",)
        if by_level["plan"]:
            cascade["plan"] = ("module", "section", "block")
        if by_level["module"]:
            cascade["module"] = ("section", "block")
        if by_level["section"]:
            cascade["section"] = ("block",)
        return {k: tuple(v) for k, v in cascade.items()}
