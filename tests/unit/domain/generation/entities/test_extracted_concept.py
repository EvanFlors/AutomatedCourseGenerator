import pytest

from src.domain.generation.entities.extracted_concept import ExtractedConcept
from src.domain.shared.exceptions.validation_error import ValidationError


class TestExtractedConcept:
    def test_creates_with_minimum_fields(self):
        c = ExtractedConcept(name="Machine Learning")

        assert c.name == "Machine Learning"
        assert c.description is None
        assert c.confidence == 1.0

    def test_creates_with_all_fields(self):
        c = ExtractedConcept(
            name="Linear Regression",
            description="A statistical method",
            confidence=0.85,
        )

        assert c.name == "Linear Regression"
        assert c.description == "A statistical method"
        assert c.confidence == 0.85

    def test_strips_whitespace_from_name(self):
        c = ExtractedConcept(name="  Supervised Learning  ")

        assert c.name == "Supervised Learning"

    def test_rejects_empty_name(self):
        with pytest.raises(ValidationError, match="name cannot be empty"):
            ExtractedConcept(name="")

    def test_rejects_whitespace_only_name(self):
        with pytest.raises(ValidationError, match="name cannot be empty"):
            ExtractedConcept(name="   ")

    def test_rejects_confidence_above_one(self):
        with pytest.raises(ValidationError, match="confidence must be"):
            ExtractedConcept(name="x", confidence=1.1)

    def test_rejects_confidence_below_zero(self):
        with pytest.raises(ValidationError, match="confidence must be"):
            ExtractedConcept(name="x", confidence=-0.1)

    def test_accepts_zero_confidence(self):
        c = ExtractedConcept(name="x", confidence=0.0)

        assert c.confidence == 0.0

    def test_equality_case_insensitive(self):
        a = ExtractedConcept(name="Machine Learning")
        b = ExtractedConcept(name="machine learning")

        assert a == b
        assert hash(a) == hash(b)

    def test_inequality_with_different_names(self):
        a = ExtractedConcept(name="ML")
        b = ExtractedConcept(name="DL")

        assert a != b

    def test_inequality_with_other_types(self):
        c = ExtractedConcept(name="x")

        assert c != "x"
        assert c != 42
