from src.domain.shared.exceptions.domain_exception import DomainException


class ConflictError(DomainException):
    def __init__(self, message: str = "Conflict error"):
        super().__init__(message)
