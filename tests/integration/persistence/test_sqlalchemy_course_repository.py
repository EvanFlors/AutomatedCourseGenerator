"""Integration tests for SqlAlchemyCourseRepository.

The repository is the only adapter that implements the domain
CourseRepository port. These tests verify the round-trip:
domain entity -> ORM model -> domain entity.
"""
import pytest

from src.domain.course.entities.content_block import ContentBlock
from src.domain.course.entities.course import Course
from src.domain.course.entities.module import Module
from src.domain.course.entities.topic import Topic
from src.domain.course.enums.block_type import BlockType
from src.infrastructure.database.repositories.sqlalchemy_course_repository import (
    SqlAlchemyCourseRepository,
)

pytestmark = pytest.mark.asyncio


def make_complex_course() -> Course:
    course = Course(
        title="ML 101",
        description="Intro to machine learning",
    )
    course.add_module(
        Module(
            title="Foundations",
            order=0,
            topics=[
                Topic(
                    title="What is ML?",
                    order=0,
                    blocks=[
                        ContentBlock(
                            block_type=BlockType.HEADING,
                            order=0,
                            payload={"text": "Intro"},
                        ),
                        ContentBlock(
                            block_type=BlockType.TEXT,
                            order=1,
                            payload={"text": "ML is..."},
                        ),
                    ],
                ),
            ],
        )
    )
    course.add_module(
        Module(
            title="Supervised",
            order=1,
            topics=[
                Topic(
                    title="Regression",
                    order=0,
                    blocks=[
                        ContentBlock(
                            block_type=BlockType.CODE,
                            order=0,
                            payload={"language": "py", "code": "x = 1"},
                        ),
                    ],
                ),
            ],
        )
    )
    return course


class TestSave:
    async def test_save_inserts_new_course(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = make_complex_course()

        await repo.save(course)
        await session.commit()

        loaded = await repo.find_by_id(course.id)
        assert loaded is not None
        assert loaded.id == course.id
        assert loaded.title == "ML 101"
        assert loaded.description == "Intro to machine learning"
        assert len(loaded.modules) == 2

    async def test_save_then_reload_preserves_full_tree(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = make_complex_course()

        await repo.save(course)
        await session.commit()
        await session.close()

        loaded = await repo.find_by_id(course.id)

        assert loaded is not None
        assert [m.title for m in loaded.modules] == ["Foundations", "Supervised"]
        assert [m.order for m in loaded.modules] == [0, 1]
        assert len(loaded.modules[0].topics) == 1
        assert loaded.modules[0].topics[0].title == "What is ML?"
        assert len(loaded.modules[0].topics[0].blocks) == 2
        assert loaded.modules[0].topics[0].blocks[0].type == BlockType.HEADING
        assert loaded.modules[0].topics[0].blocks[1].payload == {"text": "ML is..."}

    async def test_save_updates_existing_course(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = Course(title="Original", description="v1")

        await repo.save(course)
        await session.commit()

        course.title = "Updated"
        course.description = "v2"
        await repo.save(course)
        await session.commit()

        loaded = await repo.find_by_id(course.id)
        assert loaded is not None
        assert loaded.title == "Updated"
        assert loaded.description == "v2"

    async def test_save_replaces_modules_on_update(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = Course(title="T")
        course.add_module(Module(title="M1", order=0))
        course.add_module(Module(title="M2", order=1))

        await repo.save(course)
        await session.commit()

        new_course = Course(
            id=course.id,
            title="T",
            modules=[Module(title="Only M", order=0)],
        )
        await repo.save(new_course)
        await session.commit()

        loaded = await repo.find_by_id(course.id)
        assert loaded is not None
        assert [m.title for m in loaded.modules] == ["Only M"]


class TestFindById:
    async def test_returns_none_when_not_found(self, session):
        repo = SqlAlchemyCourseRepository(session)

        result = await repo.find_by_id("does-not-exist")

        assert result is None

    async def test_returns_course_with_empty_modules(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = Course(title="Empty", description="No modules")

        await repo.save(course)
        await session.commit()

        loaded = await repo.find_by_id(course.id)
        assert loaded is not None
        assert loaded.title == "Empty"
        assert loaded.modules == []


class TestListCourses:
    async def test_returns_empty_list_when_no_courses(self, session):
        repo = SqlAlchemyCourseRepository(session)

        result = await repo.list_courses()

        assert result == []

    async def test_returns_all_courses(self, session):
        repo = SqlAlchemyCourseRepository(session)

        c1 = Course(title="A")
        c2 = Course(title="B")
        c3 = Course(title="C")
        await repo.save(c1)
        await repo.save(c2)
        await repo.save(c3)
        await session.commit()

        result = await repo.list_courses()

        assert len(result) == 3
        titles = {c.title for c in result}
        assert titles == {"A", "B", "C"}

    async def test_returns_courses_with_full_tree(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = make_complex_course()
        await repo.save(course)
        await session.commit()
        await session.close()

        result = await repo.list_courses()

        assert len(result) == 1
        loaded = result[0]
        assert loaded.title == "ML 101"
        assert len(loaded.modules) == 2
        assert len(loaded.modules[0].topics) == 1
        assert len(loaded.modules[0].topics[0].blocks) == 2


class TestDelete:
    async def test_deletes_existing_course(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = make_complex_course()
        await repo.save(course)
        await session.commit()

        await repo.delete(course.id)
        await session.commit()

        loaded = await repo.find_by_id(course.id)
        assert loaded is None

    async def test_delete_is_noop_when_not_found(self, session):
        repo = SqlAlchemyCourseRepository(session)

        await repo.delete("missing-id")
        await session.commit()

        result = await repo.list_courses()
        assert result == []

    async def test_delete_cascades_to_children(self, session):
        from sqlalchemy import select

        from src.infrastructure.database.models.content_block_model import (
            ContentBlockModel,
        )
        from src.infrastructure.database.models.module_model import ModuleModel
        from src.infrastructure.database.models.topic_model import TopicModel

        repo = SqlAlchemyCourseRepository(session)
        course = make_complex_course()
        await repo.save(course)
        await session.commit()

        await repo.delete(course.id)
        await session.commit()

        for model in (ModuleModel, TopicModel, ContentBlockModel):
            result = await session.execute(select(model))
            assert result.scalars().all() == []


class TestMapping:
    async def test_payload_is_stored_as_dict(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = Course(title="T")
        course.add_module(
            Module(
                title="M",
                order=0,
                topics=[
                    Topic(
                        title="Topic",
                        order=0,
                        blocks=[
                            ContentBlock(
                                block_type=BlockType.CODE,
                                order=0,
                                payload={"language": "py", "code": "x = 1"},
                            ),
                        ],
                    ),
                ],
            )
        )

        await repo.save(course)
        await session.commit()
        await session.close()

        loaded = await repo.find_by_id(course.id)
        block = loaded.modules[0].topics[0].blocks[0]
        assert isinstance(block.payload, dict)
        assert block.payload == {"language": "py", "code": "x = 1"}

    async def test_block_type_round_trip(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = Course(title="T")
        for bt in BlockType:
            course.add_module(
                Module(
                    title=f"Module-{bt.value}",
                    order=list(BlockType).index(bt),
                    topics=[
                        Topic(
                            title="Topic",
                            order=0,
                            blocks=[
                                ContentBlock(
                                    block_type=bt,
                                    order=0,
                                    payload={"x": 1},
                                ),
                            ],
                        ),
                    ],
                )
            )

        await repo.save(course)
        await session.commit()
        await session.close()

        loaded = await repo.find_by_id(course.id)
        for module in loaded.modules:
            block = module.topics[0].blocks[0]
            assert block.type in BlockType

    async def test_save_minimal_course_with_no_description(self, session):
        repo = SqlAlchemyCourseRepository(session)
        course = Course(title="T")

        await repo.save(course)
        await session.commit()
        await session.close()

        loaded = await repo.find_by_id(course.id)
        assert loaded is not None
        assert loaded.description is None
        assert loaded.modules == []
