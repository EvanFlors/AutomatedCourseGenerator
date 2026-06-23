from __future__ import annotations

from dataclasses import dataclass, field

from cogenai.domain.course import Course
from cogenai.domain.shared.value_objects import BlockId, ModuleId, SectionId


@dataclass(frozen=True)
class DependencyGraph:

    course_to_modules: dict[str, tuple[str, ...]] = field(default_factory=dict)
    module_to_sections: dict[str, tuple[str, ...]] = field(default_factory=dict)
    section_to_blocks: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def from_course(cls, course: Course) -> "DependencyGraph":
        module_ids = tuple(str(m.id) for m in course.modules)
        module_to_sections: dict[str, tuple[str, ...]] = {}
        section_to_blocks: dict[str, tuple[str, ...]] = {}
        for module in course.modules:
            section_ids = tuple(str(s.id) for s in module.sections)
            module_to_sections[str(module.id)] = section_ids
            for section in module.sections:
                section_to_blocks[str(section.id)] = tuple(
                    str(b.id) for b in section.blocks
                )
        return cls(
            course_to_modules={str(course.id): module_ids},
            module_to_sections=module_to_sections,
            section_to_blocks=section_to_blocks,
        )

    def update_module(self, module_id: ModuleId, new_section_ids: tuple[str, ...]) -> None:
        self.module_to_sections[str(module_id)] = new_section_ids

    def update_section(self, section_id: SectionId, new_block_ids: tuple[str, ...]) -> None:
        self.section_to_blocks[str(section_id)] = new_block_ids

    def invalidate_leaves(self, module_id: ModuleId) -> tuple[str, ...]:
        section_ids = self.module_to_sections.get(str(module_id), ())
        block_ids: list[str] = []
        for sid in section_ids:
            block_ids.extend(self.section_to_blocks.get(sid, ()))
        return tuple(block_ids)

    def cascade_invalidates(self, course_id: str | None = None) -> tuple[str, ...]:
        all_block_ids: list[str] = []
        for block_ids in self.section_to_blocks.values():
            all_block_ids.extend(block_ids)
        return tuple(all_block_ids)
