from __future__ import annotations

from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.refiners.base import (
    BaseRefiner,
    BlockRefinerInput,
    BlockRefinerOutput,
    RefinementScope,
    extract_tokens,
    parse_json_response,
    validate_fields,
)


class BlockRefinerAgent(BaseRefiner[BlockRefinerInput, BlockRefinerOutput]):

    LEVEL = "block"
    TOKEN_CAP = 1000

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="block_refiner", config=config, llm_provider=llm_provider)

    def run(self, input_data: BlockRefinerInput) -> BlockRefinerOutput:
        bundle = {
            "block_id": str(input_data.current_block.id),
            "block_type": input_data.current_block.type,
            "block_order": input_data.current_block.order,
            "content_keys": list(input_data.current_block.content.keys()),
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
        validate_fields(parsed, required=("content",), level=self.LEVEL)
        refined_block = self._apply(input_data, parsed)
        self._log_execution(input_data, refined_block)
        return BlockRefinerOutput(
            block=refined_block,
            issues_addressed=tuple(parsed.get("issues_addressed", ())),
            refinement_notes=str(parsed.get("notes", "")),
            tokens_used=extract_tokens(response),
        )

    def _apply(
        self,
        input_data: BlockRefinerInput,
        parsed: dict,
    ):
        new_content = dict(input_data.current_block.content)
        new_content.update(parsed["content"])
        return input_data.current_block.with_content(
            new_content,
            new_version=input_data.current_block.version + 1,
        )

    def _make_scope(self, input_data: BlockRefinerInput) -> RefinementScope:
        return RefinementScope(
            level="block",
            target_id=str(input_data.current_block.id),
            parent_refs={"course_id": str(input_data.course_id)},
            issue_ids=tuple(i.id for i in input_data.issues),
        )
