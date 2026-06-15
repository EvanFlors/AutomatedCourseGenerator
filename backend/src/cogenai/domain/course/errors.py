class CourseError(Exception):
    """Base class for all course-related errors."""
    pass

class ValidationError(CourseError):
    """Raised when a course validation error occurs."""
    pass

class NotFoundError(CourseError):
    """Raised when a course is not found."""
    pass

class ConflictError(CourseError):
    """Raised when a course conflict error occurs."""
    pass
