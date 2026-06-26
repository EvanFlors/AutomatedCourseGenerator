import json
import re
from dataclasses import dataclass, field

from cogenai.application.agents.base import BaseAgent
from cogenai.application.agents.config import AgentConfig
from cogenai.shared.logging import get_logger
from cogenai.domain.course import Course

logger = get_logger(__name__)


@dataclass
class EvaluatorInput:
    course: Course
    rubric_version: str = "1.0.0"
    thresholds: dict | None = None


@dataclass
class RubricScores:
    accuracy: float = 0.0
    pedagogical_clarity: float = 0.0
    structure_compliance: float = 0.0
    depth_appropriateness: float = 0.0
    audience_alignment: float = 0.0
    consistency: float = 0.0
    completeness: float = 0.0


@dataclass
class EvaluationIssue:
    id: str
    severity: str
    scope: str
    target_id: str
    category: str
    message: str
    suggestion: str = ""
    auto_fixable: bool = False


@dataclass
class EvaluationThresholds:
    overall: float = 0.8
    accuracy: float = 0.7
    pedagogical_clarity: float = 0.7
    structure_compliance: float = 0.9
    depth_appropriateness: float = 0.7
    audience_alignment: float = 0.7
    consistency: float = 0.7
    completeness: float = 0.8


@dataclass
class EvaluationReport:
    overall_score: float = 0.0
    passed: bool = False
    rubric: RubricScores = field(default_factory=RubricScores)
    thresholds: EvaluationThresholds = field(default_factory=EvaluationThresholds)
    issues: tuple[EvaluationIssue, ...] = field(default_factory=tuple)
    rubric_version: str = "1.0.0"


class EvaluatorAgent(BaseAgent[EvaluatorInput, EvaluationReport]):

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="evaluator", config=config, llm_provider=llm_provider)

    def run(self, input_data: EvaluatorInput) -> EvaluationReport:
        course = input_data.course
        thresholds = input_data.thresholds or EvaluationThresholds()

        modules_summary = []
        for module in course.modules:
            sections_summary = []
            for section in module.sections:
                blocks_info = []
                for block in section.blocks:
                    block_type = block.type
                    content_keys = list(block.content.keys()) if block.content else []
                    blocks_info.append(f"Type: {block_type}, Keys: {content_keys}")
                sections_summary.append(f"{section.title}: [{'; '.join(blocks_info)}]")
            modules_summary.append(f"{module.title}: [{'; '.join(sections_summary)}]")

        user_prompt = f"""
            Evaluate this course:
            Title: {course.title}
            Summary: {course.summary}
            Outcomes: {', '.join(course.learning_outcomes)}
            Modules: {'; '.join(modules_summary)}
            Score on 7 dimensions and identify issues. Return JSON.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        rubric, issues = self._parse_evaluation(response_text, course, thresholds)

        overall_score = sum([
            rubric.accuracy, rubric.pedagogical_clarity, rubric.structure_compliance,
            rubric.depth_appropriateness, rubric.audience_alignment, rubric.consistency, rubric.completeness
        ]) / 7.0

        passed = (
            rubric.accuracy >= thresholds.accuracy and
            rubric.pedagogical_clarity >= thresholds.pedagogical_clarity and
            rubric.structure_compliance >= thresholds.structure_compliance and
            rubric.depth_appropriateness >= thresholds.depth_appropriateness and
            rubric.audience_alignment >= thresholds.audience_alignment and
            rubric.consistency >= thresholds.consistency and
            rubric.completeness >= thresholds.completeness
        )

        report = EvaluationReport(
            overall_score=overall_score,
            passed=passed,
            rubric=rubric,
            thresholds=thresholds,
            issues=issues,
            rubric_version=input_data.rubric_version,
        )
        self._log_execution(input_data, report)
        return report

    def _parse_evaluation(self, response: str, course: Course, thresholds: EvaluationThresholds) -> tuple[RubricScores, tuple[EvaluationIssue, ...]]:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            logger.warning("No JSON found in evaluator response, using defaults")
            return RubricScores(), tuple()

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            logger.warning("JSON parse failed in evaluator, using defaults")
            return RubricScores(), tuple()

        rubric_data = data.get("rubric", {})
        rubric = RubricScores(
            accuracy=rubric_data.get("accuracy", 0.7),
            pedagogical_clarity=rubric_data.get("pedagogical_clarity", 0.7),
            structure_compliance=rubric_data.get("structure_compliance", 0.5),
            depth_appropriateness=rubric_data.get("depth_appropriateness", 0.7),
            audience_alignment=rubric_data.get("audience_alignment", 0.7),
            consistency=rubric_data.get("consistency", 0.7),
            completeness=rubric_data.get("completeness", 0.5),
        )

        issues = tuple(
            EvaluationIssue(
                id=issue.get("id", f"issue-{i}"),
                severity=issue.get("severity", "warning"),
                scope=issue.get("scope", "course"),
                target_id=issue.get("target_id", str(course.id)),
                category=issue.get("category", "general"),
                message=issue.get("message", ""),
                suggestion=issue.get("suggestion", ""),
                auto_fixable=issue.get("auto_fixable", False),
            )
            for i, issue in enumerate(data.get("issues", []))
        )

        return rubric, issues
