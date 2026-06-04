"""In-memory fakes for the Neo4j driver.

These fakes emulate a small but realistic subset of the official
`neo4j` async driver's API: `AsyncDriver.session()`, `AsyncSession.run()`,
`AsyncResult.single()`, `AsyncResult.fetch_all()`, and
`AsyncResult.consume()`. They are used by unit tests to assert the
exact Cypher and parameters emitted by `Neo4jKnowledgeGraphRepository`
without requiring a running database.

Two kinds of tests rely on them:

1. **Recording-only** (default): the session records every call into
   `self.calls` and returns empty results. The test then inspects
   `calls` to verify which queries were sent. This is the simplest
   form and is what most tests use.

2. **Programmed responses**: pass a `responses` dict that maps a
   query (exact or substring) to either a list of records (static,
   returned every time the key matches) or a queue of record-lists
   (each call pops one batch, useful when the same query is run
   multiple times in a single operation).

Usage::

    driver = FakeNeo4jDriver()
    repo = Neo4jKnowledgeGraphRepository(driver)
    await repo.upsert_concept(Concept(name="X"))
    session = driver.find_session()
    assert session.find_call(substring="MERGE (c:Concept")
"""
from __future__ import annotations

from typing import Any


class FakeNeo4jResult:
    """A minimal stand-in for `neo4j.AsyncResult`."""

    def __init__(self, records: list[dict[str, Any]] | None = None):
        self._records = list(records or [])
        self._consumed = False

    async def single(self) -> dict[str, Any] | None:
        if not self._records:
            return None
        return self._records[0]

    async def fetch_all(self) -> list[dict[str, Any]]:
        return list(self._records)

    async def consume(self) -> None:
        self._consumed = True


def _is_queue_value(value: Any) -> bool:
    """A response value is a *queue* if it is a non-empty list of lists.

    A static response is a list of dicts; a queued response is a list
    of record-batches (each batch being a list of dicts).
    """
    if not isinstance(value, list) or not value:
        return False
    return all(isinstance(batch, list) for batch in value)


class FakeNeo4jSession:
    """Programmable fake that records `run` calls.

    Parameters
    ----------
    responses:
        Maps a query (exact) or substring (prefix-style) to one of:

        * a list of records (static): the same list is returned every
          time the key matches a query. Backward-compatible with the
          original `FakeNeo4jSession`.
        * a queue of record-batches (a list of lists): each call pops
          the first batch. Useful when the same query is expected to
          be sent multiple times and should return different results.

    strict:
        When True (default for new code; existing tests pass
        `strict=False` implicitly), `run` raises a `RuntimeError` if
        no programmed response matches the query. This catches
        off-by-one errors where a test expected a query but the
        repository never sent it. Set to False for recording-only
        tests.
    """

    def __init__(
        self,
        responses: dict[str, Any] | None = None,
        *,
        strict: bool = False,
    ):
        self._responses: dict[str, Any] = dict(responses or {})
        self._strict = strict
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def _consume(self, value: Any) -> list[dict[str, Any]]:
        if _is_queue_value(value):
            return value.pop(0) if value else []
        return list(value) if value else []

    def _match(self, query: str) -> list[dict[str, Any]] | None:
        """Return the records to return for `query`, or None if no key matches.

        Lookup order:

        1. Exact query (highest priority).
        2. Substring keys in insertion order (first match wins).
        """
        if query in self._responses:
            return self._consume(self._responses[query])

        for key, value in self._responses.items():
            if key and key in query:
                return self._consume(value)
        return None

    async def run(self, query: str, **parameters: Any) -> FakeNeo4jResult:
        self.calls.append((query, parameters))
        records = self._match(query)
        if records is not None:
            return FakeNeo4jResult(records)

        if self._strict:
            programmed = list(self._responses.keys())
            raise RuntimeError(
                f"No programmed response for query: {query!r}. "
                f"Programmed keys: {programmed}. "
                f"Either program a response or set strict=False."
            )
        return FakeNeo4jResult()

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> "FakeNeo4jSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def find_call(
        self,
        *,
        substring: str | None = None,
        query: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Return the first recorded call matching the given filters.

        Raises `AssertionError` with a helpful message if no call
        matches. This is a small helper to keep test code terse::

            merge_q, merge_p = session.find_call(substring="MERGE (c:Concept")
        """
        for query_, params_ in self.calls:
            if substring is not None and substring not in query_:
                continue
            if query is not None and query_ != query:
                continue
            if params is not None:
                if not all(params_.get(k) == v for k, v in params.items()):
                    continue
            return query_, params_

        raise AssertionError(
            f"No recorded call matched substring={substring!r}, "
            f"query={query!r}, params={params!r}. "
            f"Recorded calls: {[q for q, _ in self.calls]}"
        )

    def find_calls(
        self,
        *,
        substring: str | None = None,
        query: str | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Return all recorded calls matching the given filters."""
        return [
            (q, p)
            for q, p in self.calls
            if (substring is None or (substring and substring in q))
            and (query is None or q == query)
        ]


class FakeNeo4jDriver:
    """In-memory fake of `neo4j.AsyncDriver`.

    A single `FakeNeo4jDriver` can be used across multiple repository
    operations. Each call to `session()` returns a fresh
    `FakeNeo4jSession`, mirroring the real driver's behavior.
    """

    def __init__(
        self,
        responses: dict[str, Any] | None = None,
        *,
        strict: bool = False,
    ):
        self._responses = responses
        self._strict = strict
        self.sessions: list[FakeNeo4jSession] = []

    def session(self, *args: Any, **kwargs: Any) -> FakeNeo4jSession:
        session = FakeNeo4jSession(self._responses, strict=self._strict)
        self.sessions.append(session)
        return session

    def find_session(self, index: int = 0) -> FakeNeo4jSession:
        return self.sessions[index]

    def close(self) -> None:
        pass
