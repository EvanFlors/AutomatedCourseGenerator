"""Integration tests for SQLAlchemy models and their relationships.

These tests use an in-memory SQLite database (see conftest.py) and verify
that the models work together as expected: persistence, relationships,
cascading deletes, and column constraints.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.infrastructure.database.models.content_block_model import ContentBlockModel
from src.infrastructure.database.models.course_model import CourseModel
from src.infrastructure.database.models.module_model import ModuleModel
from src.infrastructure.database.models.topic_model import TopicModel


pytestmark = pytest.mark.asyncio


class TestCourseModel:
    async def test_persists_minimal_course(self, session):
        course = CourseModel(id="c1", title="Intro to AI")

        session.add(course)
        await session.commit()

        result = await session.execute(
            select(CourseModel).where(CourseModel.id == "c1")
        )
        loaded = result.scalar_one()

        assert loaded.title == "Intro to AI"
        assert loaded.description is None
        assert loaded.created_at is not None
        assert loaded.updated_at is not None

    async def test_persists_course_with_description(self, session):
        course = CourseModel(
            id="c1",
            title="ML",
            description="Machine learning foundations",
        )

        session.add(course)
        await session.commit()

        loaded = await session.get(CourseModel, "c1")
        assert loaded.description == "Machine learning foundations"

    async def test_title_is_required(self, session):
        course = CourseModel(id="c1", title=None)

        session.add(course)

        with pytest.raises(IntegrityError):
            await session.commit()


class TestModuleModel:
    async def test_module_requires_course(self, session):
        module = ModuleModel(
            id="m1",
            course_id="missing",
            title="M1",
            order=0,
        )

        session.add(module)

        with pytest.raises(IntegrityError):
            await session.commit()

    async def test_cascade_delete_module_when_course_deleted(self, session):
        course = CourseModel(id="c1", title="ML")
        module = ModuleModel(id="m1", course_id="c1", title="M1", order=0)
        course.modules.append(module)

        session.add(course)
        await session.commit()

        await session.delete(await session.get(CourseModel, "c1"))
        await session.commit()

        result = await session.execute(select(ModuleModel))
        assert result.scalars().all() == []


class TestTopicModel:
    async def test_topic_requires_module(self, session):
        topic = TopicModel(
            id="t1",
            module_id="missing",
            title="T1",
            order=0,
        )

        session.add(topic)

        with pytest.raises(IntegrityError):
            await session.commit()

    async def test_cascade_delete_topic_when_module_deleted(self, session):
        course = CourseModel(id="c1", title="ML")
        module = ModuleModel(id="m1", course_id="c1", title="M1", order=0)
        topic = TopicModel(id="t1", module_id="m1", title="T1", order=0)
        module.topics.append(topic)
        course.modules.append(module)

        session.add(course)
        await session.commit()

        await session.delete(await session.get(CourseModel, "c1"))
        await session.commit()

        result = await session.execute(select(TopicModel))
        assert result.scalars().all() == []


class TestContentBlockModel:
    async def test_block_requires_topic(self, session):
        block = ContentBlockModel(
            id="b1",
            topic_id="missing",
            type="text",
            order=0,
            payload={"text": "hi"},
        )

        session.add(block)

        with pytest.raises(IntegrityError):
            await session.commit()

    async def test_block_persists_json_payload(self, session):
        course = CourseModel(id="c1", title="ML")
        module = ModuleModel(id="m1", course_id="c1", title="M1", order=0)
        topic = TopicModel(id="t1", module_id="m1", title="T1", order=0)
        block = ContentBlockModel(
            id="b1",
            topic_id="t1",
            type="code",
            order=0,
            payload={"language": "python", "code": "print(1)"},
        )
        topic.blocks.append(block)
        module.topics.append(topic)
        course.modules.append(module)

        session.add(course)
        await session.commit()

        loaded = await session.get(ContentBlockModel, "b1")
        assert loaded.payload == {"language": "python", "code": "print(1)"}
        assert loaded.type == "code"

    async def test_cascade_delete_blocks_full_chain(self, session):
        course = CourseModel(id="c1", title="ML")
        module = ModuleModel(id="m1", course_id="c1", title="M1", order=0)
        topic = TopicModel(id="t1", module_id="m1", title="T1", order=0)
        block = ContentBlockModel(
            id="b1",
            topic_id="t1",
            type="text",
            order=0,
            payload={"text": "hi"},
        )
        topic.blocks.append(block)
        module.topics.append(topic)
        course.modules.append(module)

        session.add(course)
        await session.commit()

        await session.delete(await session.get(CourseModel, "c1"))
        await session.commit()

        for model in (ModuleModel, TopicModel, ContentBlockModel):
            result = await session.execute(select(model))
            assert result.scalars().all() == []


class TestRelationshipLoading:
    async def test_eager_loading_returns_full_tree(self, session):
        from sqlalchemy.orm import selectinload

        course = CourseModel(id="c1", title="ML")
        module = ModuleModel(id="m1", course_id="c1", title="M1", order=0)
        topic = TopicModel(id="t1", module_id="m1", title="T1", order=0)
        block = ContentBlockModel(
            id="b1",
            topic_id="t1",
            type="text",
            order=0,
            payload={"text": "hi"},
        )
        topic.blocks.append(block)
        module.topics.append(topic)
        course.modules.append(module)

        session.add(course)
        await session.commit()

        result = await session.execute(
            select(CourseModel)
            .where(CourseModel.id == "c1")
            .options(
                selectinload(CourseModel.modules)
                .selectinload(ModuleModel.topics)
                .selectinload(TopicModel.blocks)
            )
        )
        loaded = result.scalar_one()

        assert loaded.title == "ML"
        assert len(loaded.modules) == 1
        assert loaded.modules[0].title == "M1"
        assert len(loaded.modules[0].topics) == 1
        assert loaded.modules[0].topics[0].title == "T1"
        assert len(loaded.modules[0].topics[0].blocks) == 1
        assert loaded.modules[0].topics[0].blocks[0].payload == {"text": "hi"}

    async def test_modules_returned_in_order_when_queried(self, session):
        from sqlalchemy.orm import selectinload

        course = CourseModel(id="c1", title="ML")
        course.modules.extend([
            ModuleModel(id="m3", title="M3", order=2),
            ModuleModel(id="m1", title="M1", order=0),
            ModuleModel(id="m2", title="M2", order=1),
        ])

        session.add(course)
        await session.commit()
        await session.close()

        result = await session.execute(
            select(CourseModel)
            .options(selectinload(CourseModel.modules))
        )
        loaded = result.scalar_one()

        assert [m.order for m in loaded.modules] == [0, 1, 2]
