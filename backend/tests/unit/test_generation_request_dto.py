from __future__ import annotations

import pytest
from pydantic import ValidationError

from cogenai.interfaces.dto.generation_request import GenerationRequestDTO


class TestGenerationRequestDTO:
    def test_minimal_required_fields(self):
        r = GenerationRequestDTO(
            topic="Python",
            learning_outcomes=("Variables",),
        )
        assert r.topic == "Python"
        assert r.audience == "beginner"
        assert r.difficulty == "beginner"
        assert r.max_iterations == 3

    def test_immutability(self):
        r = GenerationRequestDTO(topic="X", learning_outcomes=("A",))
        with pytest.raises(ValidationError):
            r.topic = "Y"  # type: ignore[misc]

    def test_model_copy_creates_new_instance(self):
        r = GenerationRequestDTO(topic="X", learning_outcomes=("A",), num_modules=1)
        r2 = r.model_copy(update={"num_modules": 5})
        assert r.num_modules == 1
        assert r2.num_modules == 5
        assert r is not r2

    def test_invalid_audience_rejected(self):
        with pytest.raises(ValidationError):
            GenerationRequestDTO(
                topic="X",
                audience="wizard",
                learning_outcomes=("A",),
            )

    def test_invalid_difficulty_rejected(self):
        with pytest.raises(ValidationError):
            GenerationRequestDTO(
                topic="X",
                difficulty="guru",
                learning_outcomes=("A",),
            )

    def test_empty_outcomes_rejected(self):
        with pytest.raises(ValidationError):
            GenerationRequestDTO(topic="X", learning_outcomes=())

    def test_blank_outcome_stripped(self):
        r = GenerationRequestDTO(
            topic="X",
            learning_outcomes=("A", "", "  ", "B"),
        )
        assert r.learning_outcomes == ("A", "B")

    def test_block_types_coerced_from_list(self):
        r = GenerationRequestDTO(
            topic="X",
            learning_outcomes=("A",),
            block_types=["quiz", "code"],
        )
        assert r.block_types == ("quiz", "code")
        assert isinstance(r.block_types, tuple)

    def test_num_modules_bounds(self):
        with pytest.raises(ValidationError):
            GenerationRequestDTO(topic="X", learning_outcomes=("A",), num_modules=0)
        with pytest.raises(ValidationError):
            GenerationRequestDTO(topic="X", learning_outcomes=("A",), num_modules=21)

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            GenerationRequestDTO(
                topic="X",
                learning_outcomes=("A",),
                surprise_field="oops",
            )

    def test_with_updates_helper(self):
        r = GenerationRequestDTO(topic="X", learning_outcomes=("A",))
        r2 = r.with_updates(num_modules=3)
        assert r2.num_modules == 3
        assert r.num_modules is None  # LLM-chooses by default

    def test_default_factory(self):
        r = GenerationRequestDTO.default()
        assert r.topic == "Python"
        assert r.audience == "beginner"
        assert "Variables" in r.learning_outcomes
