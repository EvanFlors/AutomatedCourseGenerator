from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from cogenai.prompt import get_prompt, load_prompts


PROMPT_DIR = Path(__file__).resolve().parents[2] / "src" / "cogenai" / "prompt"


@pytest.mark.parametrize("yaml_file", sorted(PROMPT_DIR.glob("*.yml")))
def test_every_prompt_yaml_has_schema(yaml_file: Path):
    """Every YAML prompt must declare a `schema:` block (Sprint 6 lock-in)."""
    data = yaml.safe_load(yaml_file.read_text()) or {}
    assert "schema" in data, f"{yaml_file.name}: missing 'schema:' block"
    schema = data["schema"]
    assert isinstance(schema, dict), f"{yaml_file.name}: 'schema' must be a mapping"
    assert schema.get("type") in ("object", "array"), (
        f"{yaml_file.name}: root schema must be object or array"
    )


@pytest.mark.parametrize("yaml_file", sorted(PROMPT_DIR.glob("*.yml")))
def test_every_prompt_yaml_is_valid_against_loader(yaml_file: Path):
    """Every YAML must load cleanly via the production loader."""
    # Use a fresh tmp dir so we don't pollute the global _PROMPTS state.
    with tempfile.TemporaryDirectory() as tmp:
        # Copy just this file into a temp dir to isolate from auto-loading.
        target = Path(tmp) / yaml_file.name
        target.write_text(yaml_file.read_text())
        load_prompts(tmp)
        bundle = get_prompt(yaml_file.stem)
        assert bundle is not None, f"{yaml_file.name}: failed to load"
        assert bundle.has_schema(), f"{yaml_file.name}: bundle has no schema"


def test_all_built_in_prompts_have_schemas():
    """Sanity check: the built-in prompt directory loads with 17/17 schemas."""
    import cogenai.prompt as p
    p.ensure_loaded()
    bundles = [b for vs in p._PROMPTS.values() for b in vs.values()]
    assert len(bundles) >= 17
    missing = [b.name for b in bundles if not b.has_schema()]
    assert missing == [], f"bundles missing schemas: {missing}"