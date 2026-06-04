import pytest

from src.domain.course.entities.module import Module
from src.domain.course.entities.topic import Topic
from src.domain.shared.exceptions.validation_error import ValidationError


class TestModuleInstantiation:
    def test_creates_module_with_minimal_data(self, sample_module_title):
        module = Module(title=sample_module_title, order=0)

        assert module.id is not None
        assert module.title == sample_module_title
        assert module.order == 0
        assert module.topics == []

    def test_creates_module_with_topics(self):
        t1 = Topic(title="T1", order=0)
        t2 = Topic(title="T2", order=1)

        module = Module(title="M", order=0, topics=[t1, t2])

        assert module.topics == [t1, t2]

    def test_strips_whitespace_from_title(self):
        module = Module(title="  Padded  ", order=0)

        assert module.title == "Padded"

    def test_generates_uuid_id_when_not_provided(self):
        module = Module(title="M", order=0)

        assert isinstance(module.id, str)
        assert len(module.id) == 36

    def test_preserves_provided_id(self):
        module = Module(title="M", order=0, id="custom-id")

        assert module.id == "custom-id"

    def test_accepts_zero_order(self):
        module = Module(title="M", order=0)

        assert module.order == 0


class TestModuleValidation:
    def test_raises_validation_error_on_empty_title(self):
        with pytest.raises(ValidationError, match="title cannot be empty"):
            Module(title="", order=0)

    def test_raises_validation_error_on_whitespace_title(self):
        with pytest.raises(ValidationError, match="title cannot be empty"):
            Module(title="   ", order=0)

    def test_raises_validation_error_on_negative_order(self):
        with pytest.raises(ValidationError, match="order cannot be negative"):
            Module(title="M", order=-1)


class TestModuleTopicManagement:
    def test_add_topic_appends_to_list(self):
        module = Module(title="M", order=0)
        topic = Topic(title="T", order=0)

        module.add_topic(topic)

        assert module.topics == [topic]

    def test_add_topic_keeps_topics_sorted_by_order(self):
        module = Module(title="M", order=0)
        t1 = Topic(title="T1", order=2)
        t2 = Topic(title="T2", order=0)
        t3 = Topic(title="T3", order=1)

        module.add_topic(t1)
        module.add_topic(t2)
        module.add_topic(t3)

        assert [t.order for t in module.topics] == [0, 1, 2]

    def test_remove_topic_filters_by_id(self):
        module = Module(title="M", order=0)
        t1 = Topic(title="T1", order=0)
        t2 = Topic(title="T2", order=1)
        module.add_topic(t1)
        module.add_topic(t2)

        module.remove_topic(t1.id)

        assert module.topics == [t2]

    def test_remove_nonexistent_topic_leaves_list_unchanged(self):
        module = Module(title="M", order=0)
        t1 = Topic(title="T1", order=0)
        module.add_topic(t1)

        module.remove_topic("missing-id")

        assert module.topics == [t1]

    def test_get_topic_returns_matching_topic(self):
        module = Module(title="M", order=0)
        t1 = Topic(title="T1", order=0)
        module.add_topic(t1)

        assert module.get_topic(t1.id) is t1

    def test_get_topic_returns_none_when_not_found(self):
        module = Module(title="M", order=0)

        assert module.get_topic("missing") is None
