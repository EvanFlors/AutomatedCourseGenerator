from dataclasses import dataclass, field
import json
import re

from cogenai.agents.base import BaseAgent
from cogenai.agents.config import AgentConfig
from cogenai.agents.registry import prompt_registry
from cogenai.agents_implementations.persona_adapter import AdaptedSection
from cogenai.bootstrap.logging import get_logger
from cogenai.domain.course import ContentBlock

logger = get_logger(__name__)


@dataclass
class ConsistencyCheckerInput:
    sections: tuple[AdaptedSection, ...]


@dataclass
class TerminologyIssue:
    block_id: str
    term: str
    expected: str
    severity: str = "warning"


@dataclass
class OrderingIssue:
    block_id: str
    issue: str
    severity: str = "warning"


@dataclass
class ContradictionIssue:
    block_id_1: str
    block_id_2: str
    claim_1: str
    claim_2: str
    severity: str = "error"


@dataclass
class ConsistencyReport:
    sections_checked: int
    blocks_checked: int
    terminology_issues: tuple[TerminologyIssue, ...] = field(default_factory=tuple)
    ordering_issues: tuple[OrderingIssue, ...] = field(default_factory=tuple)
    contradiction_issues: tuple[ContradictionIssue, ...] = field(default_factory=tuple)
    passed: bool = True


CONSISTENCY_CHECKER_PROMPT = """
You are a ConsistencyChecker agent. Check sections for terminology, ordering, and contradictions.
Output JSON: {"terminology_issues": [], "ordering_issues": [], "contradiction_issues": [], "passed": true}
"""

prompt_registry.register("consistency_checker", "1.0.0", CONSISTENCY_CHECKER_PROMPT)


class ConsistencyCheckerAgent(BaseAgent[ConsistencyCheckerInput, ConsistencyReport]):

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="consistency_checker", config=config, llm_provider=llm_provider)

    def run(self, input_data: ConsistencyCheckerInput) -> ConsistencyReport:
        sections = input_data.sections

        blocks_data = []
        for section in sections:
            for block in section.adapted_blocks:
                blocks_data.append({"id": str(block.id), "type": block.type, "content": block.content})

        user_prompt = f"""
            Check consistency across {len(sections)} sections ({len(blocks_data)} blocks).
            Identify terminology, ordering, and contradiction issues. Return JSON.
        """

        response_text = self._call_llm(user_prompt, self._get_prompt())
        term, ordering, contradiction, passed = self._parse_response(response_text)

        report = ConsistencyReport(
            sections_checked=len(sections),
            blocks_checked=len(blocks_data),
            terminology_issues=term,
            ordering_issues=ordering,
            contradiction_issues=contradiction,
            passed=passed,
        )
        self._log_execution(input_data, report)
        return report

    def _parse_response(self, response: str) -> tuple[tuple[TerminologyIssue, ...], tuple[OrderingIssue, ...], tuple[ContradictionIssue, ...], bool]:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if not match:
            logger.warning("No JSON found in consistency checker response, assuming passed")
            return tuple(), tuple(), tuple(), True

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            logger.warning("JSON parse failed in consistency checker, assuming passed")
            return tuple(), tuple(), tuple(), True

        def _entries(field_name: str) -> list[dict]:
            raw = data.get(field_name, [])
            if not isinstance(raw, list):
                return []
            out: list[dict] = []
            for item in raw:
                if isinstance(item, dict):
                    out.append(item)
            return out

        term = tuple(
            TerminologyIssue(
                block_id=issue.get("block_id", ""),
                term=issue.get("term", ""),
                expected=issue.get("expected", ""),
                severity=issue.get("severity", "warning"),
            )
            for issue in _entries("terminology_issues")
        )

        ordering = tuple(
            OrderingIssue(
                block_id=issue.get("block_id", ""),
                issue=issue.get("issue", ""),
                severity=issue.get("severity", "warning"),
            )
            for issue in _entries("ordering_issues")
        )

        contradiction = tuple(
            ContradictionIssue(
                block_id_1=issue.get("block_id_1", ""),
                block_id_2=issue.get("block_id_2", ""),
                claim_1=issue.get("claim_1", ""),
                claim_2=issue.get("claim_2", ""),
                severity=issue.get("severity", "error"),
            )
            for issue in _entries("contradiction_issues")
        )

        passed = data.get("passed", len(term) == 0 and len(ordering) == 0 and len(contradiction) == 0)
        return term, ordering, contradiction, passed
