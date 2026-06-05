from enum import Enum


class CourseLevel(str, Enum):
    """Difficulty/target level for a generated course."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
