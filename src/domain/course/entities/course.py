from uuid import uuid4

from src.domain.course.entities.module import Module
from src.domain.shared.exceptions.validation_error import ValidationError


class Course:

    def __init__(
        self,
        title: str,
        description: str | None = None,
        modules: list[Module] | None = None,
        id: str | None = None,
    ):
        self.id = id or str(uuid4())
        self.title = title.strip()
        self.modules = modules or []
        self.description = (
            description.strip()
            if description
            else None
        )
        self._validate()

    def _validate(self):

        if not self.title:
            raise ValidationError("Course title cannot be empty.")

    def add_module(self, module: Module):

        self.modules.append(module)

        self._sort_modules()

    def remove_module(self, module_id: str):

        self.modules = [
            module
            for module in self.modules
            if module.id != module_id
        ]

    def get_module(self, module_id: str):

        return next(
            (
                module
                for module in self.modules
                if module.id == module_id
            ),
            None
        )

    def _sort_modules(self):

        self.modules.sort(
            key=lambda module: module.order
        )