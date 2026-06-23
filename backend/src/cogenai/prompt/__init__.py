from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PromptBundle:
    name: str
    version: str
    description: str
    system_prompt: str
    user_prompt: str


_PROMPTS: dict[str, dict[str, PromptBundle]] = {}
_LOADED = False


def _default_prompt_dir() -> Path:
    """Default location of the YAML prompts directory (sibling of the cogenai package)."""
    return Path(__file__).resolve().parent


def ensure_loaded() -> None:
    """Load YAML prompts from the default directory if not already loaded.

    Idempotent. Safe to call multiple times.
    """
    global _LOADED
    if _LOADED:
        return
    load_prompts(_default_prompt_dir())
    _LOADED = True


def load_prompts(directory: Path | str) -> int:
    """Load all *.yml files from `directory` into the in-memory registry.

    Returns the number of prompts loaded. Idempotent: re-loading replaces entries.
    """
    path = Path(directory)
    if not path.exists():
        return 0
    count = 0
    for yml_file in sorted(path.glob("*.yml")):
        with yml_file.open("r", encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f) or {}
        bundle = PromptBundle(
            name=str(data.get("name", yml_file.stem)),
            version=str(data.get("version", "1.0.0")),
            description=str(data.get("description", "")),
            system_prompt=str(data.get("system_prompt", "")).strip(),
            user_prompt=str(data.get("user_prompt", "")).strip(),
        )
        _PROMPTS.setdefault(bundle.name, {})[bundle.version] = bundle
        count += 1
    return count


def get_prompt(name: str, version: str = "1.0.0") -> PromptBundle | None:
    ensure_loaded()
    return _PROMPTS.get(name, {}).get(version)


def has_prompt(name: str, version: str = "1.0.0") -> bool:
    return get_prompt(name, version) is not None


def render_user_prompt(template: str, **kwargs: Any) -> str:
    """Replace {key} placeholders in the user-prompt template.

    Unknown keys are left as-is (preserves literal braces in the LLM prompt).
    """
    def _sub(match: re.Match) -> str:
        key = match.group(1)
        return str(kwargs[key]) if key in kwargs else match.group(0)
    return re.sub(r"\{(\w+)\}", _sub, template)
