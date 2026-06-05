from abc import ABC, abstractmethod

from src.domain.course.entities.course import Course


class CourseRepository(ABC):

    @abstractmethod
    async def save(
        self,
        course: Course
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def find_by_id(
        self,
        course_id: str
    ) -> Course | None:
        raise NotImplementedError

    @abstractmethod
    async def list_courses(
        self
    ) -> list[Course]:
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        course_id: str
    ) -> None:
        raise NotImplementedError
