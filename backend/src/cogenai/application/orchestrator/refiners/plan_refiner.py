from __future__ import annotations

from cogenai.application.agents.config import AgentConfig
from cogenai.application.orchestrator.curriculum_planner import (
    CourseSkeleton,
    ModuleSpec,
    Prerequisite,
    SectionSpec,
)
from cogenai.application.orchestrator.refiners.base import (
    BaseRefiner,
    PlanRefinerInput,
    PlanRefinerOutput,
    RefinementScope,
    extract_tokens,
    parse_json_response,
    validate_fields,
)


VALID_PREREQ_TYPES = {"requires", "builds_on", "enables"}


def merge_plan(current: CourseSkeleton, llm_modules: list[dict]) -> tuple[tuple[ModuleSpec, ...], tuple[int, ...]]:
    existing_by_title = {m.title: (i, m) for i, m in enumerate(current.modules)}
    seen_titles: set[str] = set()
    merged: list[ModuleSpec] = []
    affected: list[int] = []
    for spec_dict in llm_modules:
        title = str(spec_dict.get("title", "")).strip()
        if not title:
            continue
        order = int(spec_dict.get("order", len(merged)))
        topics = tuple(spec_dict.get("topics", ()))
        summary = str(spec_dict.get("summary", ""))
        new_spec = ModuleSpec(title=title, summary=summary, order=order, topics=topics)
        if title in existing_by_title:
            idx, _ = existing_by_title[title]
            if title not in seen_titles:
                merged.append(new_spec)
                seen_titles.add(title)
                affected.append(len(merged) - 1)
        else:
            merged.append(new_spec)
            seen_titles.add(title)
            affected.append(len(merged) - 1)
    for original_title, (original_idx, original_spec) in existing_by_title.items():
        if original_title not in seen_titles:
            merged.append(original_spec)
            seen_titles.add(original_title)
    return tuple(merged), tuple(affected)


class PlanRefinerAgent(BaseRefiner[PlanRefinerInput, PlanRefinerOutput]):

    LEVEL = "plan"
    TOKEN_CAP = 1500

    def __init__(self, config: AgentConfig, llm_provider):
        super().__init__(name="plan_refiner", config=config, llm_provider=llm_provider)

    def run(self, input_data: PlanRefinerInput) -> PlanRefinerOutput:
        plan = input_data.current_plan
        bundle = {
            "plan_topic": plan.topic,
            "modules": [f"{m.title} (order={m.order})" for m in plan.modules],
            "sections_count": len(plan.sections),
            "prerequisites_count": len(plan.prerequisites),
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
        merged_modules, affected_indices = merge_plan(plan, parsed.get("modules", []))
        merged_sections = self._merge_sections(plan, parsed.get("sections", []))
        merged_prereqs = self._parse_prereqs(parsed.get("prerequisites", []))
        merged_plan = CourseSkeleton(
            topic=plan.topic,
            modules=merged_modules,
            sections=merged_sections,
            prerequisites=merged_prereqs,
            learning_objectives_mapping=plan.learning_objectives_mapping,
        )
        self._log_execution(input_data, merged_plan)
        return PlanRefinerOutput(
            plan=merged_plan,
            affected_module_ids=affected_indices,
            issues_addressed=tuple(parsed.get("issues_addressed", ())),
            refinement_notes=str(parsed.get("notes", "")),
            tokens_used=extract_tokens(response),
        )

    def _merge_sections(
        self,
        plan: CourseSkeleton,
        llm_sections: list[dict],
    ) -> tuple[SectionSpec, ...]:
        existing_titles = {s.title: s for s in plan.sections}
        seen: set[str] = set()
        merged: list[SectionSpec] = []
        for spec_dict in llm_sections:
            title = str(spec_dict.get("title", "")).strip()
            if not title:
                continue
            objectives = tuple(spec_dict.get("learning_objectives", ()))
            new_spec = SectionSpec(
                title=title,
                topic=str(spec_dict.get("topic", "")),
                order=int(spec_dict.get("order", len(merged))),
                learning_objectives=objectives,
            )
            if title in existing_titles:
                if title not in seen:
                    merged.append(new_spec)
                    seen.add(title)
            else:
                merged.append(new_spec)
                seen.add(title)
        for original_title, original_spec in existing_titles.items():
            if original_title not in seen:
                merged.append(original_spec)
                seen.add(original_title)
        return tuple(merged)

    def _parse_prereqs(self, llm_prereqs: list[dict]) -> tuple[Prerequisite, ...]:
        result: list[Prerequisite] = []
        for entry in llm_prereqs:
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
                Prerequisite(from_topic=from_topic, to_topic=to_topic, type=prereq_type)
            )
        return tuple(result)

    def _make_scope(self, input_data: PlanRefinerInput) -> RefinementScope:
        return RefinementScope(
            level="plan",
            target_id=str(input_data.course_id),
            parent_refs={"course_id": str(input_data.course_id)},
            issue_ids=tuple(i.id for i in input_data.issues),
        )
