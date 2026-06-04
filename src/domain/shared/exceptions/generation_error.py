from src.domain.shared.exceptions.domain_exception import DomainException


class GenerationError(DomainException):
    def __init__(self, message: str = "Course generation failed"):
        super().__init__(message)
