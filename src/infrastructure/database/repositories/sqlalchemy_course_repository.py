from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.course.entities.content_block import ContentBlock
from src.domain.course.entities.course import Course
from src.domain.course.entities.module import Module
from src.domain.course.entities.topic import Topic
from src.domain.course.enums.block_type import BlockType
from src.domain.course.repositories.course_repository import CourseRepository
from src.infrastructure.database.models.content_block_model import ContentBlockModel
from src.infrastructure.database.models.course_model import CourseModel
from src.infrastructure.database.models.module_model import ModuleModel
from src.infrastructure.database.models.topic_model import TopicModel


class SqlAlchemyCourseRepository(CourseRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, course: Course) -> None:
        existing = await self._session.get(
            CourseModel,
            course.id,
            options=[
                selectinload(CourseModel.modules)
                .selectinload(ModuleModel.topics)
                .selectinload(TopicModel.blocks),
            ],
        )

        if existing is not None:
            await self._session.delete(existing)
            await self._session.flush()

        course_model = self._to_course_model(course)
        self._session.add(course_model)
        await self._session.flush()

    async def find_by_id(self, course_id: str) -> Course | None:
        stmt = (
            select(CourseModel)
            .where(CourseModel.id == course_id)
            .options(
                selectinload(CourseModel.modules)
                .selectinload(ModuleModel.topics)
                .selectinload(TopicModel.blocks)
            )
        )
        result = await self._session.execute(stmt)
        course_model = result.scalar_one_or_none()

        if course_model is None:
            return None

        return self._to_course_entity(course_model)

    async def list_courses(self) -> list[Course]:
        stmt = (
            select(CourseModel)
            .options(
                selectinload(CourseModel.modules)
                .selectinload(ModuleModel.topics)
                .selectinload(TopicModel.blocks)
            )
            .order_by(CourseModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        course_models = result.scalars().all()

        return [self._to_course_entity(m) for m in course_models]

    async def delete(self, course_id: str) -> None:
        course_model = await self._session.get(CourseModel, course_id)
        if course_model is not None:
            await self._session.delete(course_model)
            await self._session.flush()

    def _to_course_model(self, course: Course) -> CourseModel:
        return CourseModel(
            id=course.id,
            title=course.title,
            description=course.description,
            modules=[self._to_module_model(m) for m in course.modules],
        )

    def _to_module_model(self, module: Module) -> ModuleModel:
        return ModuleModel(
            id=module.id,
            title=module.title,
            order=module.order,
            topics=[self._to_topic_model(t) for t in module.topics],
        )

    def _to_topic_model(self, topic: Topic) -> TopicModel:
        return TopicModel(
            id=topic.id,
            title=topic.title,
            order=topic.order,
            blocks=[self._to_content_block_model(b) for b in topic.blocks],
        )

    def _to_content_block_model(self, block: ContentBlock) -> ContentBlockModel:
        return ContentBlockModel(
            id=block.id,
            type=block.type.value,
            order=block.order,
            payload=dict(block.payload),
        )

    def _to_course_entity(self, model: CourseModel) -> Course:
        course = Course(
            id=model.id,
            title=model.title,
            description=model.description,
        )
        for module_model in model.modules:
            course.add_module(self._to_module_entity(module_model))
        return course

    def _to_module_entity(self, model: ModuleModel) -> Module:
        module = Module(
            id=model.id,
            title=model.title,
            order=model.order,
        )
        for topic_model in model.topics:
            module.add_topic(self._to_topic_entity(topic_model))
        return module

    def _to_topic_entity(self, model: TopicModel) -> Topic:
        topic = Topic(
            id=model.id,
            title=model.title,
            order=model.order,
        )
        for block_model in model.blocks:
            topic.add_block(self._to_content_block_entity(block_model))
        return topic

    def _to_content_block_entity(self, model: ContentBlockModel) -> ContentBlock:
        return ContentBlock(
            id=model.id,
            block_type=BlockType(model.type),
            order=model.order,
            payload=dict(model.payload) if model.payload else {},
        )
