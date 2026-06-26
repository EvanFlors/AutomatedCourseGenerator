from __future__ import annotations

from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.refiners.base import (
    BaseRefiner,
    ModuleRefinerInput,
    ModuleRefinerOutput,
    RefinementScope,
    extract_tokens,
    parse_json_response,
    validate_fields,
)


class ModuleRefinerAgent(BaseRefiner[ModuleRefinerInput, ModuleRefinerOutput]):

    LEVEL = "module"
    TOKEN_CAP = 2000

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="module_refiner", config=config, llm_provider=llm_provider)

    def run(self, input_data: ModuleRefinerInput) -> ModuleRefinerOutput:
        bundle = {
            "module_id": str(input_data.current_module.id),
            "module_title": input_data.current_module.title,
            "module_summary": input_data.current_module.summary,
            "sections_count": len(input_data.current_module.sections),
            "course_outline": "; ".join(input_data.course_outline),
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
        return ModuleRefinerOutput(
            module=refined,
            issues_addressed=tuple(parsed.get("issues_addressed", ())),
            refinement_notes=str(parsed.get("notes", "")),
            tokens_used=extract_tokens(response),
        )

    def _apply(
        self,
        input_data: ModuleRefinerInput,
        parsed: dict,
    ):
        from cogenai.domain.course import Module

        new_title = str(parsed["title"]).strip() or input_data.current_module.title
        new_summary = str(parsed.get("summary", input_data.current_module.summary))
        refined = Module(
            id=input_data.current_module.id,
            title=new_title,
            summary=new_summary,
            order=input_data.current_module.order,
            sections=list(input_data.current_module.sections),
        )
        return refined.with_sections(
            tuple(refined.sections),
            new_version=refined.version + 1,
        )

    def _make_scope(self, input_data: ModuleRefinerInput) -> RefinementScope:
        return RefinementScope(
            level="module",
            target_id=str(input_data.current_module.id),
            parent_refs={"course_id": str(input_data.course_id)},
            issue_ids=tuple(i.id for i in input_data.issues),
        )
