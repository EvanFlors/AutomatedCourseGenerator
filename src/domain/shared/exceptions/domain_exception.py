class DomainException(Exception):
    def __init__(self, message: str = "Domain error"):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message
