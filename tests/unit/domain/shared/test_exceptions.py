import pytest

from src.domain.shared.exceptions import (
    ConflictError,
    DomainException,
    GenerationError,
    NotFoundError,
    ValidationError,
)
from src.domain.shared.exceptions.conflict_error import ConflictError as ConflictErrorDirect
from src.domain.shared.exceptions.domain_exception import DomainException as DomainExceptionDirect
from src.domain.shared.exceptions.generation_error import GenerationError as GenerationErrorDirect
from src.domain.shared.exceptions.not_found_error import NotFoundError as NotFoundErrorDirect
from src.domain.shared.exceptions.validation_error import ValidationError as ValidationErrorDirect


class TestDomainExceptionBase:
    def test_is_exception_subclass(self):
        assert issubclass(DomainException, Exception)

    def test_default_message(self):
        exc = DomainException()

        assert exc.message == "Domain error"
        assert str(exc) == "Domain error"

    def test_custom_message(self):
        exc = DomainException("Something went wrong")

        assert exc.message == "Something went wrong"
        assert str(exc) == "Something went wrong"

    def test_can_be_raised_and_caught(self):
        with pytest.raises(DomainException, match="custom error"):
            raise DomainException("custom error")


class TestExceptionHierarchy:
    @pytest.mark.parametrize(
        "child_class",
        [ValidationError, NotFoundError, ConflictError, GenerationError],
    )
    def test_all_specific_exceptions_inherit_from_domain_exception(self, child_class):
        assert issubclass(child_class, DomainException)

    @pytest.mark.parametrize(
        "child_class",
        [ValidationError, NotFoundError, ConflictError, GenerationError],
    )
    def test_all_specific_exceptions_are_catchable_as_domain_exception(self, child_class):
        with pytest.raises(DomainException):
            raise child_class("test")

    @pytest.mark.parametrize(
        "child_class",
        [ValidationError, NotFoundError, ConflictError, GenerationError],
    )
    def test_all_specific_exceptions_are_catchable_as_exception(self, child_class):
        with pytest.raises(Exception):
            raise child_class("test")


class TestValidationError:
    def test_default_message(self):
        exc = ValidationError()

        assert exc.message == "Validation error"
        assert str(exc) == "Validation error"

    def test_custom_message(self):
        exc = ValidationError("Field X is required")

        assert exc.message == "Field X is required"

    def test_inherits_from_domain_exception(self):
        assert issubclass(ValidationError, DomainException)


class TestNotFoundError:
    def test_default_message(self):
        exc = NotFoundError()

        assert exc.message == "Resource not found"

    def test_custom_message(self):
        exc = NotFoundError("Course with id X not found")

        assert exc.message == "Course with id X not found"

    def test_inherits_from_domain_exception(self):
        assert issubclass(NotFoundError, DomainException)


class TestConflictError:
    def test_default_message(self):
        exc = ConflictError()

        assert exc.message == "Conflict error"

    def test_custom_message(self):
        exc = ConflictError("Email already in use")

        assert exc.message == "Email already in use"

    def test_inherits_from_domain_exception(self):
        assert issubclass(ConflictError, DomainException)


class TestGenerationError:
    def test_default_message(self):
        exc = GenerationError()

        assert exc.message == "Course generation failed"

    def test_custom_message(self):
        exc = GenerationError("LLM rate limit exceeded")

        assert exc.message == "LLM rate limit exceeded"

    def test_inherits_from_domain_exception(self):
        assert issubclass(GenerationError, DomainException)


class TestExceptionsPublicApi:
    def test_all_exposed_classes_are_subclasses_of_domain_exception(self):
        for cls in [ValidationError, NotFoundError, ConflictError, GenerationError]:
            assert issubclass(cls, DomainException)

    def test_public_api_classes_match_direct_imports(self):
        assert ValidationError is ValidationErrorDirect
        assert NotFoundError is NotFoundErrorDirect
        assert ConflictError is ConflictErrorDirect
        assert GenerationError is GenerationErrorDirect
        assert DomainException is DomainExceptionDirect
