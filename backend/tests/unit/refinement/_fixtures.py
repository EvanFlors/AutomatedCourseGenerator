from __future__ import annotations

from dataclasses import dataclass

from cogenai.agents_implementations.evaluator import EvaluationIssue
from cogenai.domain.value_objects.llm import CompletionResponse, CompletionUsage, Model


def make_issue(
    issue_id: str = "i-1",
    severity: str = "warning",
    scope: str = "block",
    target_id: str = "block-1",
    category: str = "completeness",
    message: str = "Sample issue.",
) -> EvaluationIssue:
    return EvaluationIssue(
        id=issue_id,
        severity=severity,
        scope=scope,
        target_id=target_id,
        category=category,
        message=message,
        suggestion="",
        auto_fixable=False,
    )


def make_issues(*specs: tuple[str, str, str, str]) -> tuple[EvaluationIssue, ...]:
    out = []
    for spec in specs:
        issue_id, scope, target_id, category = spec
        out.append(make_issue(issue_id=issue_id, scope=scope, target_id=target_id, category=category))
    return tuple(out)


@dataclass
class FakeProvider:
    returns: str = "{}"
    call_count: int = 0

    def health_check(self) -> bool:
        return True

    def complete(self, request) -> CompletionResponse:
        self.call_count += 1
        return CompletionResponse(
            text=self.returns,
            model=request.model,
            usage=CompletionUsage(
                input_tokens=10,
                output_tokens=len(self.returns) // 4,
                total_tokens=10 + len(self.returns) // 4,
            ),
            finish_reason="stop",
        )


def make_block_response(content: dict, issues=("i-1",)) -> str:
    import json
    return json.dumps({"content": content, "issues_addressed": list(issues), "notes": "ok"})


def make_section_response(title: str, objectives, issues=("i-1",)) -> str:
    import json
    return json.dumps(
        {"title": title, "learning_objectives": objectives, "issues_addressed": list(issues), "notes": "ok"}
    )


def make_module_response(title: str, summary: str, issues=("i-1",)) -> str:
    import json
    return json.dumps({"title": title, "summary": summary, "issues_addressed": list(issues), "notes": "ok"})


def make_context_response(
    audience: str = "beginner",
    difficulty: str = "beginner",
    outcomes=("Variables",),
    instructions: str = "",
    issues=("i-1",),
) -> str:
    import json
    return json.dumps(
        {
            "audience": audience,
            "difficulty": difficulty,
            "learning_outcomes": list(outcomes),
            "text_instructions": instructions,
            "issues_addressed": list(issues),
            "notes": "ok",
        }
    )


def make_prereqs_response(prereqs, issues=("i-1",)) -> str:
    import json
    return json.dumps({"prerequisites": prereqs, "issues_addressed": list(issues), "notes": "ok"})


def make_plan_response(
    modules,
    sections=None,
    prereqs=None,
    issues=("i-1",),
) -> str:
    import json
    return json.dumps(
        {
            "modules": modules,
            "sections": sections or [],
            "prerequisites": prereqs or [],
            "issues_addressed": list(issues),
            "notes": "ok",
        }
    )


def make_metadata_response(
    tags=("python", "beginner", "tutorial"),
    language: str = "en",
    issues=("i-1",),
) -> str:
    import json
    return json.dumps(
        {
            "tags": list(tags),
            "language": language,
            "issues_addressed": list(issues),
            "notes": "ok",
        }
    )


class StubProvider:
    def health_check(self) -> bool:
        return True

    def complete(self, request) -> CompletionResponse:
        return CompletionResponse(
            text='{"ok": true}',
            model=request.model,
            usage=CompletionUsage(0, 0, 0),
            finish_reason="stop",
        )


def _config():
    from cogenai.agents.config import AgentConfig
    return AgentConfig.default(model_name="stub-model")
