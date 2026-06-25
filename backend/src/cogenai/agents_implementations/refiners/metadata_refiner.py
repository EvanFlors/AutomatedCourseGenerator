from __future__ import annotations

from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.refiners.base import (
    BaseRefiner,
    MetadataRefinerInput,
    MetadataRefinerOutput,
    RefinementScope,
    extract_tokens,
    parse_json_response,
    validate_fields,
)

VALID_LANGUAGES = {"en", "es", "fr", "de", "ja", "zh"}
MIN_TAGS = 3
MAX_TAGS = 5


def _normalize_tag(raw: str) -> str:
    return raw.strip().strip("#").lower().replace(" ", "-")


def _compute_duration_minutes(course_or_bundle) -> int:
    """Deterministic: sum block.estimated_time_minutes over all sections/modules.

    Works on either a Course entity or a CourseBundle.
    """
    course = getattr(course_or_bundle, "course", course_or_bundle)
    modules = getattr(course, "modules", ())
    total = 0
    for module in modules:
        for section in getattr(module, "sections", ()):
            for block in getattr(section, "blocks", ()):
                total += int(getattr(block, "estimated_time_minutes", 0) or 0)
    return total


class MetadataRefinerAgent(BaseRefiner[MetadataRefinerInput, MetadataRefinerOutput]):

    LEVEL = "metadata"
    TOKEN_CAP = 600

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="metadata_refiner", config=config, llm_provider=llm_provider)

    def run(self, input_data: MetadataRefinerInput) -> MetadataRefinerOutput:
        bundle = {
            "course_topic": input_data.topic,
            "course_audience": input_data.audience,
            "course_difficulty": input_data.difficulty,
            "current_tags": list(input_data.current_tags),
            "current_language": input_data.current_language,
            "current_duration_minutes": input_data.current_duration_minutes,
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
        validate_fields(parsed, required=("tags", "language"), level=self.LEVEL)
        new_tags, new_language = self._apply(input_data, parsed)
        self._log_execution(input_data, new_tags)
        return MetadataRefinerOutput(
            tags=new_tags,
            language=new_language,
            estimated_duration_minutes=input_data.current_duration_minutes,
            issues_addressed=tuple(parsed.get("issues_addressed", ())),
            refinement_notes=str(parsed.get("notes", "")),
            tokens_used=extract_tokens(response),
        )

    def _apply(
        self,
        input_data: MetadataRefinerInput,
        parsed: dict,
    ) -> tuple[tuple[str, ...], str]:
        raw_tags = parsed.get("tags", [])
        if not isinstance(raw_tags, list):
            raw_tags = []
        normalized: list[str] = []
        for raw in raw_tags:
            tag = _normalize_tag(str(raw))
            if tag and tag not in normalized:
                normalized.append(tag)
            if len(normalized) >= MAX_TAGS:
                break
        while len(normalized) < MIN_TAGS and input_data.current_tags:
            candidate = _normalize_tag(input_data.current_tags[len(normalized)])
            if candidate and candidate not in normalized:
                normalized.append(candidate)
            else:
                break
        if not normalized:
            normalized = list(input_data.current_tags)

        language = str(parsed.get("language", input_data.current_language)).lower()
        if language not in VALID_LANGUAGES:
            language = input_data.current_language or "en"

        return tuple(normalized), language

    def _make_scope(self, input_data: MetadataRefinerInput) -> RefinementScope:
        return RefinementScope(
            level="metadata",
            target_id=str(input_data.course_id),
            parent_refs={"course_id": str(input_data.course_id)},
            issue_ids=tuple(i.id for i in input_data.issues),
        )
