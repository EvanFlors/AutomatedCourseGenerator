from src.domain.shared.exceptions.domain_exception import DomainException


class ValidationError(DomainException):
    def __init__(self, message: str = "Validation error"):
        super().__init__(message)
