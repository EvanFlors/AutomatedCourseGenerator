"""Quick-start templates per FR-CG-002.

Each template pre-fills topic / audience / outcomes / block_types. Templates
live as JSON files alongside this module and are loaded at startup. The CLI
flag `--template NAME` and the API query param `?template=NAME` apply a
template to a fresh `GenerationRequestDTO`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class CourseTemplate:
    name: str
    description: str
    topic: str
    audience: str
    difficulty: str
    learning_outcomes: tuple[str, ...]
    block_types: tuple[str, ...]
    strategy: str = "fundamental learning"
    num_modules: int = 4
    sections_per_module: int = 3

    def apply(self, request: dict[str, Any]) -> dict[str, Any]:
        """Overlay template fields onto a request payload (template wins)."""
        out = dict(request)
        out.update({
            "topic": self.topic,
            "audience": self.audience,
            "difficulty": self.difficulty,
            "learning_outcomes": list(self.learning_outcomes),
            "block_types": list(self.block_types),
            "strategy": self.strategy,
            "num_modules": self.num_modules,
            "sections_per_module": self.sections_per_module,
        })
        return out


def load_templates(directory: Path | None = None) -> dict[str, CourseTemplate]:
    """Load all *.json templates from the given directory."""
    directory = directory or TEMPLATES_DIR
    out: dict[str, CourseTemplate] = {}
    if not directory.exists():
        return out
    for fp in sorted(directory.glob("*.json")):
        with fp.open("r", encoding="utf-8") as f:
            data = json.load(f)
        out[data["name"]] = CourseTemplate(
            name=data["name"],
            description=data.get("description", ""),
            topic=data["topic"],
            audience=data["audience"],
            difficulty=data["difficulty"],
            learning_outcomes=tuple(data["learning_outcomes"]),
            block_types=tuple(data.get("block_types", ("concept", "example", "exercise"))),
            strategy=data.get("strategy", "fundamental learning"),
            num_modules=int(data.get("num_modules", 4)),
            sections_per_module=int(data.get("sections_per_module", 3)),
        )
    return out


_TEMPLATES: dict[str, CourseTemplate] | None = None


def get_template(name: str) -> CourseTemplate | None:
    """Return the template with the given name, or None."""
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = load_templates()
    return _TEMPLATES.get(name)


def list_templates() -> list[str]:
    """Return all available template names, sorted."""
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = load_templates()
    return sorted(_TEMPLATES.keys())


def reset_template_cache() -> None:
    """Force a reload (used by tests)."""
    global _TEMPLATES
    _TEMPLATES = None