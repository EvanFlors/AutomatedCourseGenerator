from src.domain.generation.value_objects.source_type import SourceType


class TestSourceType:
    def test_values(self):
        assert SourceType.TEXT.value == "text"
        assert SourceType.URL.value == "url"
        assert SourceType.YOUTUBE.value == "youtube"
        assert SourceType.PDF.value == "pdf"

    def test_str_inheritance(self):
        assert str(SourceType.TEXT) == "SourceType.TEXT"
        assert SourceType.TEXT == "text"

    def test_iteration(self):
        values = {st.value for st in SourceType}
        assert values == {"text", "url", "youtube", "pdf"}
