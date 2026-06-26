from __future__ import annotations

import pytest

from cogenai.application.templates import (
    CourseTemplate,
    get_template,
    list_templates,
    load_templates,
    reset_template_cache,
)
from cogenai.interfaces.dto.generation_request import GenerationRequestDTO


class TestTemplates:
    def test_python_beginner_loads(self):
        reset_template_cache()
        tmpl = get_template("python-beginner")
        assert tmpl is not None
        assert tmpl.topic == "Python"
        assert tmpl.audience == "beginner"
        assert "Variables" in tmpl.learning_outcomes

    def test_rust_advanced_loads(self):
        reset_template_cache()
        tmpl = get_template("rust-advanced")
        assert tmpl is not None
        assert tmpl.difficulty == "advanced"
        assert "Ownership" in tmpl.learning_outcomes

    def test_unknown_template_returns_none(self):
        reset_template_cache()
        assert get_template("does-not-exist") is None

    def test_list_templates_returns_sorted(self):
        reset_template_cache()
        names = list_templates()
        assert names == sorted(names)
        assert "python-beginner" in names
        assert "rust-advanced" in names

    def test_apply_overlays_topic_and_outcomes(self):
        reset_template_cache()
        tmpl = get_template("python-beginner")
        base = GenerationRequestDTO(topic="X", learning_outcomes=("y",))
        out = tmpl.apply(base.model_dump())
        assert out["topic"] == "Python"
        assert "Variables" in out["learning_outcomes"]

    def test_apply_does_not_lose_extra_fields(self):
        reset_template_cache()
        tmpl = get_template("python-beginner")
        base = {
            "topic": "X",
            "learning_outcomes": ["y"],
            "max_iterations": 5,
        }
        out = tmpl.apply(base)
        assert out["max_iterations"] == 5  # not overwritten

    def test_load_all_templates(self):
        reset_template_cache()
        all_t = load_templates()
        assert len(all_t) >= 2
        for name, tmpl in all_t.items():
            assert isinstance(tmpl, CourseTemplate)
            assert tmpl.name == name