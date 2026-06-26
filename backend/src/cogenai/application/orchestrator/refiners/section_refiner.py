from __future__ import annotations

from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.refiners.base import (
    BaseRefiner,
    RefinementScope,
    SectionRefinerInput,
    SectionRefinerOutput,
    extract_tokens,
    parse_json_response,
    validate_fields,
)


class SectionRefinerAgent(BaseRefiner[SectionRefinerInput, SectionRefinerOutput]):

    LEVEL = "section"
    TOKEN_CAP = 1500

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="section_refiner", config=config, llm_provider=llm_provider)

    def run(self, input_data: SectionRefinerInput) -> SectionRefinerOutput:
        bundle = {
            "section_id": str(input_data.current_section.id),
            "section_title": input_data.current_section.title,
            "section_order": input_data.current_section.order,
            "learning_objectives": list(input_data.current_section.learning_objectives),
            "blocks_count": len(input_data.current_section.blocks),
            "module_outline": "; ".join(input_data.module_outline),
            "issues": "\n".join(
                f"- [{i.severity}] {i.category}: {i.message}" for i in input_data.issues
            ),
        }
        user_prompt = self._build_prompt(
            scope=self._make_scope(input_data),
            bundle=bundle,
            issue_text=bundle["issues"],
        )
        response = self._call_llm_full(user_prompt, self._get_prompt(), bundle=self._get_prompt_bundle())
        parsed = parse_json_response(response.text, level=self.LEVEL)
        validate_fields(parsed, required=("title",), level=self.LEVEL)
        refined = self._apply(input_data, parsed)
        self._log_execution(input_data, refined)
        return SectionRefinerOutput(
            section=refined,
            issues_addressed=tuple(parsed.get("issues_addressed", ())),
            refinement_notes=str(parsed.get("notes", "")),
            tokens_used=extract_tokens(response),
        )

    def _apply(
        self,
        input_data: SectionRefinerInput,
        parsed: dict,
    ):
        from cogenai.domain.course import Section

        new_objectives = list(parsed.get("learning_objectives", input_data.current_section.learning_objectives))
        new_title = str(parsed["title"]).strip() or input_data.current_section.title
        refined = Section(
            id=input_data.current_section.id,
            title=new_title,
            order=input_data.current_section.order,
            blocks=list(input_data.current_section.blocks),
            learning_objectives=new_objectives,
        )
        return refined.with_blocks(
            list(refined.blocks),
            new_version=refined.version + 1,
        )

    def _make_scope(self, input_data: SectionRefinerInput) -> RefinementScope:
        return RefinementScope(
            level="section",
            target_id=str(input_data.current_section.id),
            parent_refs={"course_id": str(input_data.course_id)},
            issue_ids=tuple(i.id for i in input_data.issues),
        )
