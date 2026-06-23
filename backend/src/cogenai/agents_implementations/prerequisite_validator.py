from dataclasses import dataclass, field
import json
import re

from cogenai.agents.base import BaseAgent
from cogenai.agents.config import AgentConfig
from cogenai.agents.registry import prompt_registry
from cogenai.agents_implementations.curriculum_planner import CourseSkeleton
from cogenai.bootstrap.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PrerequisiteValidatorInput:
    skeleton: CourseSkeleton


@dataclass
class PrerequisiteIssue:
    topic: str
    missing_prerequisite: str
    severity: str = "error"


@dataclass
class OrderingIssue:
    topic_1: str
    topic_2: str
    issue: str
    severity: str = "warning"


@dataclass
class ProgressionReport:
    sections_checked: int
    prerequisites_satisfied: bool
    missing_prerequisites: tuple[PrerequisiteIssue, ...] = field(default_factory=tuple)
    ordering_issues: tuple[OrderingIssue, ...] = field(default_factory=tuple)
    passed: bool = True


PREREQUISITE_VALIDATOR_PROMPT = """
You are a PrerequisiteValidator agent. Check the course progression for missing prerequisites and ordering issues.
Output JSON: {"missing_prerequisites": [{"topic":"","missing_prerequisite":"","severity":""}], "ordering_issues": [{"topic_1":"","topic_2":"","issue":"","severity":""}], "passed": true}
"""

prompt_registry.register("prerequisite_validator", "1.0.0", PREREQUISITE_VALIDATOR_PROMPT)


class PrerequisiteValidatorAgent(BaseAgent[PrerequisiteValidatorInput, ProgressionReport]):

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="prerequisite_validator", config=config, llm_provider=llm_provider)

    def run(self, input_data: PrerequisiteValidatorInput) -> ProgressionReport:
        skeleton = input_data.skeleton

        user_prompt = f"""
            Validate the progression of this course skeleton:
            Modules: {len(skeleton.modules)}, Sections: {len(skeleton.sections)}
            Prerequisites: {len(skeleton.prerequisites)}
            Identify missing prerequisites and ordering issues. Return JSON.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        missing, ordering, passed = self._parse_response(response_text)

        report = ProgressionReport(
            sections_checked=len(skeleton.sections),
            prerequisites_satisfied=passed,
            missing_prerequisites=missing,
            ordering_issues=ordering,
            passed=passed,
        )
        self._log_execution(input_data, report)
        return report

    def _parse_response(self, response: str) -> tuple[tuple[PrerequisiteIssue, ...], tuple[OrderingIssue, ...], bool]:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            logger.warning("No JSON found in prerequisite validator, assuming passed")
            return tuple(), tuple(), True

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            logger.warning("JSON parse failed in prerequisite validator, assuming passed")
            return tuple(), tuple(), True

        missing = tuple(
            PrerequisiteIssue(
                topic=issue.get("topic", ""),
                missing_prerequisite=issue.get("missing_prerequisite", ""),
                severity=issue.get("severity", "error"),
            )
            for issue in data.get("missing_prerequisites", [])
        )

        ordering = tuple(
            OrderingIssue(
                topic_1=issue.get("topic_1", ""),
                topic_2=issue.get("topic_2", ""),
                issue=issue.get("issue", ""),
                severity=issue.get("severity", "warning"),
            )
            for issue in data.get("ordering_issues", [])
        )

        passed = data.get("passed", len(missing) == 0 and len(ordering) == 0)
        return missing, ordering, passed
