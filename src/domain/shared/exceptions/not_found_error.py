from src.domain.shared.exceptions.domain_exception import DomainException


class NotFoundError(DomainException):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message)
