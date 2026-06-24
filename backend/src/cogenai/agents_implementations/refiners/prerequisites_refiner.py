from __future__ import annotations

from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.curriculum_planner import Prerequisite
from cogenai.agents_implementations.refiners.base import (
    BaseRefiner,
    PrerequisitesRefinerInput,
    PrerequisitesRefinerOutput,
    RefinementScope,
    extract_tokens,
    parse_json_response,
    validate_fields,
)


VALID_PREREQ_TYPES = {"requires", "builds_on", "enables"}


class PrerequisitesRefinerAgent(BaseRefiner[PrerequisitesRefinerInput, PrerequisitesRefinerOutput]):

    LEVEL = "prerequisites"
    TOKEN_CAP = 600

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="prerequisites_refiner", config=config, llm_provider=llm_provider)

    def run(self, input_data: PrerequisitesRefinerInput) -> PrerequisitesRefinerOutput:
        bundle = {
            "course_topic": input_data.course_topic,
            "prerequisites": "; ".join(
                f"{p.from_topic} -> {p.to_topic}" for p in input_data.current_prerequisites
            ),
            "issues": "\n".join(
                f"- [{i.severity}] {i.category}: {i.message}" for i in input_data.issues
            ),
        }
        user_prompt = self._build_prompt(
            scope=self._make_scope(input_data),
            bundle=bundle,
            issue_text=bundle["issues"],
        )
        response = self._call_llm_full(user_prompt, self._get_prompt())
        parsed = parse_json_response(response.text, level=self.LEVEL)
        validate_fields(parsed, required=("prerequisites",), level=self.LEVEL)
        refined = self._apply(parsed)
        self._log_execution(input_data, refined)
        return PrerequisitesRefinerOutput(
            prerequisites=refined,
            issues_addressed=tuple(parsed.get("issues_addressed", ())),
            refinement_notes=str(parsed.get("notes", "")),
            tokens_used=extract_tokens(response),
        )

    def _apply(self, parsed: dict) -> tuple[Prerequisite, ...]:
        result: list[Prerequisite] = []
        for entry in parsed.get("prerequisites", []):
            if not isinstance(entry, dict):
                continue
            from_topic = str(entry.get("from_topic", "")).strip()
            to_topic = str(entry.get("to_topic", "")).strip()
            if not from_topic or not to_topic:
                continue
            prereq_type = str(entry.get("type", "requires")).lower()
            if prereq_type not in VALID_PREREQ_TYPES:
                prereq_type = "requires"
            result.append(
                Prerequisite(
                    from_topic=from_topic,
                    to_topic=to_topic,
                    type=prereq_type,
                )
            )
        return tuple(result)

    def _make_scope(self, input_data: PrerequisitesRefinerInput) -> RefinementScope:
        return RefinementScope(
            level="prerequisites",
            target_id=str(input_data.course_id),
            parent_refs={"course_id": str(input_data.course_id)},
            issue_ids=tuple(i.id for i in input_data.issues),
        )
