from __future__ import annotations

from cogenai.agents.config import AgentConfig
from cogenai.agents.registry import prompt_registry
from cogenai.agents_implementations.context_synthesizer import GenerationContext
from cogenai.agents_implementations.refiners.base import (
    BaseRefiner,
    ContextRefinerInput,
    ContextRefinerOutput,
    RefinementScope,
    extract_tokens,
    parse_json_response,
    validate_fields,
)


CONTEXT_REFINER_PROMPT = """
You are a ContextRefiner agent.
Refine the course context: audience, difficulty, outcomes, instructions.

OUTPUT RULES (do NOT violate):
- The topic field is IMMUTABLE. Never change it.
- Preserve document and reference_courses arrays.
- Return valid JSON only. If the response would be truncated, omit optional fields rather than producing invalid JSON.

OUTPUT FORMAT (JSON object):
{
  "audience": "beginner|professional|engineer|architect|manager|researcher|student",
  "difficulty": "beginner|intermediate|advanced|expert",
  "learning_outcomes": ["..."],
  "text_instructions": "...",
  "issues_addressed": ["id1", ...],
  "notes": "short explanation"
}
""".strip()


prompt_registry.register("context_refiner", "1.0.0", CONTEXT_REFINER_PROMPT)


VALID_AUDIENCE = {"beginner", "professional", "engineer", "architect", "manager", "researcher", "student"}
VALID_DIFFICULTY = {"beginner", "intermediate", "advanced", "expert"}


class ContextRefinerAgent(BaseRefiner[ContextRefinerInput, ContextRefinerOutput]):

    LEVEL = "context"
    TOKEN_CAP = 800

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="context_refiner", config=config, llm_provider=llm_provider)

    def run(self, input_data: ContextRefinerInput) -> ContextRefinerOutput:
        ctx = input_data.current_context
        bundle = {
            "context_topic": ctx.topic,
            "context_audience": ctx.audience,
            "context_difficulty": ctx.difficulty,
            "context_outcomes": list(ctx.learning_outcomes),
            "context_instructions": ctx.text_instructions,
            "user_feedback": input_data.user_feedback,
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
        refined_ctx = self._apply(input_data, parsed)
        self._log_execution(input_data, refined_ctx)
        return ContextRefinerOutput(
            context=refined_ctx,
            issues_addressed=tuple(parsed.get("issues_addressed", ())),
            refinement_notes=str(parsed.get("notes", "")),
            tokens_used=extract_tokens(response),
        )

    def _apply(
        self,
        input_data: ContextRefinerInput,
        parsed: dict,
    ):
        ctx = input_data.current_context
        audience = str(parsed.get("audience", ctx.audience)).lower()
        if audience not in VALID_AUDIENCE:
            audience = ctx.audience
        difficulty = str(parsed.get("difficulty", ctx.difficulty)).lower()
        if difficulty not in VALID_DIFFICULTY:
            difficulty = ctx.difficulty
        outcomes = parsed.get("learning_outcomes", list(ctx.learning_outcomes))
        if not isinstance(outcomes, list) or not outcomes:
            outcomes = list(ctx.learning_outcomes)
        instructions = str(parsed.get("text_instructions", ctx.text_instructions))
        if input_data.user_feedback:
            instructions = instructions + f"\n[refined] {input_data.user_feedback}"
        return GenerationContext(
            topic=ctx.topic,
            audience=audience,
            difficulty=difficulty,
            learning_outcomes=tuple(outcomes),
            text_instructions=instructions,
            documents=ctx.documents,
            reference_courses=ctx.reference_courses,
            domain_knowledge=ctx.domain_knowledge,
        )

    def _make_scope(self, input_data: ContextRefinerInput) -> RefinementScope:
        return RefinementScope(
            level="context",
            target_id=str(input_data.course_id),
            parent_refs={"course_id": str(input_data.course_id)},
            issue_ids=tuple(i.id for i in input_data.issues),
        )
