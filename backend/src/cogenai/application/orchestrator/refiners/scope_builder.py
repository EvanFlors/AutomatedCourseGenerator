from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from cogenai.application.orchestrator.evaluator import EvaluationIssue
from cogenai.application.orchestrator.refiners.base import (
    RefinementLevel,
    RefinementScope,
    TokenCapExceeded,
)

if TYPE_CHECKING:
    from cogenai.domain.course import ContentBlock, Course, Module, Section


@dataclass(frozen=True)
class ScopeBundle:
    scope: RefinementScope
    payload: dict
    estimated_tokens: int


class ScopeBuilder:

    TOKEN_CAPS: dict[RefinementLevel, int] = {
        "context": 800,
        "prerequisites": 600,
        "plan": 1500,
        "module": 2000,
        "section": 1500,
        "block": 1000,
    }

    def estimate_tokens(self, payload: dict) -> int:
        total_chars = sum(len(str(v)) for v in payload.values())
        return total_chars // 4

    def cap_for(self, level: RefinementLevel) -> int:
        return self.TOKEN_CAPS[level]

    def build(
        self,
        level: RefinementLevel,
        target_id: str,
        target_object: object,
        issues: tuple[EvaluationIssue, ...],
        parent_refs: dict[str, str] | None = None,
        siblings: tuple[str, ...] = (),
        constraints: tuple[str, ...] = (),
        pass_rate: float = 0.8,
    ) -> ScopeBundle:
        parent_refs = parent_refs or {}
        issue_ids = tuple(i.id for i in issues)
        issue_text = "\n".join(
            f"- [{i.severity}] {i.category}: {i.message}" for i in issues
        )
        payload = self._serialize(level, target_object, siblings, issue_text)
        estimated = self.estimate_tokens(payload)
        cap = self.cap_for(level)
        if estimated > cap:
            payload = self._trim(level, target_object, siblings, issue_text)
            estimated = self.estimate_tokens(payload)
            if estimated > cap:
                raise TokenCapExceeded(level=level, estimated_tokens=estimated, cap=cap)
        scope = RefinementScope(
            level=level,
            target_id=target_id,
            parent_refs=dict(parent_refs),
            sibling_summaries={f"sibling_{i}": s for i, s in enumerate(siblings)},
            issue_ids=issue_ids,
            constraints=constraints,
            pass_rate=pass_rate,
        )
        return ScopeBundle(scope=scope, payload=payload, estimated_tokens=estimated)

    def _serialize(
        self,
        level: RefinementLevel,
        target_object: object,
        siblings: tuple[str, ...],
        issue_text: str,
    ) -> dict:
        if level == "context":
            return self._serialize_context(target_object, siblings, issue_text)
        if level == "prerequisites":
            return self._serialize_prerequisites(target_object, siblings, issue_text)
        if level == "plan":
            return self._serialize_plan(target_object, siblings, issue_text)
        if level == "module":
            return self._serialize_module(target_object, siblings, issue_text)
        if level == "section":
            return self._serialize_section(target_object, siblings, issue_text)
        if level == "block":
            return self._serialize_block(target_object, siblings, issue_text)
        return {"issues": issue_text}

    def _serialize_context(self, ctx, siblings, issues) -> dict:
        return {
            "context_topic": getattr(ctx, "topic", ""),
            "context_audience": getattr(ctx, "audience", ""),
            "context_difficulty": getattr(ctx, "difficulty", ""),
            "context_outcomes": list(getattr(ctx, "learning_outcomes", ())),
            "context_instructions": getattr(ctx, "text_instructions", ""),
            "issues": issues,
        }

    def _serialize_prerequisites(self, prereqs, siblings, issues) -> dict:
        prereq_lines = [f"{p.from_topic} -> {p.to_topic}" for p in prereqs]
        return {
            "prerequisites": "; ".join(prereq_lines),
            "course_topic": siblings[0] if siblings else "",
            "issues": issues,
        }

    def _serialize_plan(self, plan, siblings, issues) -> dict:
        return {
            "plan_topic": getattr(plan, "topic", ""),
            "modules": [
                f"{m.title} (order={m.order})" for m in getattr(plan, "modules", ())
            ],
            "sections_count": len(getattr(plan, "sections", ())),
            "prerequisites_count": len(getattr(plan, "prerequisites", ())),
            "issues": issues,
        }

    def _serialize_module(self, module, siblings, issues) -> dict:
        return {
            "module_id": str(getattr(module, "id", "")),
            "module_title": getattr(module, "title", ""),
            "module_summary": getattr(module, "summary", ""),
            "module_order": getattr(module, "order", 0),
            "sections_count": len(getattr(module, "sections", ())),
            "course_outline": "; ".join(siblings),
            "issues": issues,
        }

    def _serialize_section(self, section, siblings, issues) -> dict:
        return {
            "section_id": str(getattr(section, "id", "")),
            "section_title": getattr(section, "title", ""),
            "section_order": getattr(section, "order", 0),
            "learning_objectives": list(getattr(section, "learning_objectives", [])),
            "blocks_count": len(getattr(section, "blocks", ())),
            "module_outline": "; ".join(siblings),
            "issues": issues,
        }

    def _serialize_block(self, block, siblings, issues) -> dict:
        content_keys = list(getattr(block, "content", {}).keys())
        return {
            "block_id": str(getattr(block, "id", "")),
            "block_type": getattr(block, "type", ""),
            "block_order": getattr(block, "order", 0),
            "content_keys": content_keys,
            "difficulty": getattr(block, "difficulty", ""),
            "section_outline": "; ".join(siblings),
            "issues": issues,
        }

    def _trim(
        self,
        level: RefinementLevel,
        target_object: object,
        siblings: tuple[str, ...],
        issue_text: str,
    ) -> dict:
        return {
            "target_id": str(getattr(target_object, "id", "")),
            "target_type": level,
            "siblings_count": len(siblings),
            "issues": issue_text,
        }
