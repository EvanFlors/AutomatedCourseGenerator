import pytest

from src.infrastructure.integrations.chunking.simple_chunker import SimpleChunker


class TestShortText:
    def test_returns_single_chunk_for_short_text(self):
        chunker = SimpleChunker(chunk_size=2000, overlap=200)
        text = "Short text."

        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].index == 0
        assert chunks[0].start_char == 0
        assert chunks[0].end_char == len(text)

    def test_empty_text_returns_empty_list(self):
        chunker = SimpleChunker()

        assert chunker.chunk("") == []


class TestLongText:
    def test_chunks_long_text_into_overlapping_windows(self):
        chunker = SimpleChunker(chunk_size=100, overlap=20)
        text = "a" * 350

        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.text) <= 100
            assert chunk.text == text[chunk.start_char:chunk.end_char]
            assert chunk.index >= 0

    def test_advances_by_step_size(self):
        chunker = SimpleChunker(chunk_size=100, overlap=20)
        text = "a" * 500

        chunks = chunker.chunk(text)

        for i in range(1, len(chunks)):
            assert chunks[i].start_char > chunks[i - 1].start_char

    def test_covers_full_text(self):
        chunker = SimpleChunker(chunk_size=100, overlap=20)
        text = "abcdefghij" * 100

        chunks = chunker.chunk(text)

        first_start = chunks[0].start_char
        last_end = chunks[-1].end_char
        assert first_start == 0
        assert last_end == len(text)

    def test_indices_are_zero_based_and_sequential(self):
        chunker = SimpleChunker(chunk_size=100, overlap=20)
        text = "a" * 500

        chunks = chunker.chunk(text)

        assert [c.index for c in chunks] == list(range(len(chunks)))


class TestSentenceBoundaries:
    def test_breaks_at_paragraph_boundary_when_present(self):
        chunker = SimpleChunker(chunk_size=50, overlap=10)
        text = "Sentence one. " + "x" * 30 + ".\n\n" + "Sentence two. " + "y" * 30

        chunks = chunker.chunk(text)

        first_chunk = chunks[0]
        assert first_chunk.end_char < len(text)
        assert first_chunk.end_char <= 50

    def test_falls_back_to_hard_cut_when_no_boundary(self):
        chunker = SimpleChunker(chunk_size=50, overlap=10)
        text = "a" * 200

        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        assert all(len(c.text) <= 50 for c in chunks)


class TestSourceIndex:
    def test_propagates_source_index_to_chunks(self):
        chunker = SimpleChunker(chunk_size=100, overlap=20)
        text = "a" * 250

        chunks = chunker.chunk(text, source_index=3)

        assert all(c.source_index == 3 for c in chunks)


class TestConfiguration:
    def test_rejects_zero_chunk_size(self):
        with pytest.raises(ValueError, match="chunk_size must be positive"):
            SimpleChunker(chunk_size=0)

    def test_rejects_negative_overlap(self):
        with pytest.raises(ValueError, match="overlap must be"):
            SimpleChunker(chunk_size=100, overlap=-1)

    def test_rejects_overlap_equal_to_chunk_size(self):
        with pytest.raises(ValueError, match="overlap must be"):
            SimpleChunker(chunk_size=100, overlap=100)

    def test_rejects_overlap_larger_than_chunk_size(self):
        with pytest.raises(ValueError, match="overlap must be"):
            SimpleChunker(chunk_size=100, overlap=200)
