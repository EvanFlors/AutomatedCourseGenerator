from uuid import uuid4

from src.domain.course.entities.topic import Topic
from src.domain.shared.exceptions.validation_error import ValidationError


class Module:

    def __init__(
        self,
        title: str,
        order: int,
        topics: list[Topic] | None = None,
        id: str | None = None,
    ):
        self.id = id or str(uuid4())
        self.title = title.strip()
        self.order = order
        self.topics = topics or []
        self._validate()

    def _validate(self):

        if not self.title:
            raise ValidationError("Module title cannot be empty.")

        if self.order < 0:
            raise ValidationError("Module order cannot be negative.")

    def add_topic(self, topic: Topic):

        self.topics.append(topic)

        self._sort_topics()

    def remove_topic(self, topic_id: str):

        self.topics = [
            topic for topic in self.topics
            if topic.id != topic_id
        ]

    def get_topic(self, topic_id: str):

        return next(
            (
                topic
                for topic in self.topics
                if topic.id == topic_id
            ),
            None
        )

    def _sort_topics(self):

        self.topics.sort(key=lambda topic: topic.order)