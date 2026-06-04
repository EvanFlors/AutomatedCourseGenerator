"""Database fixtures for integration tests.

Uses an in-memory SQLite engine that is created once per test, with all
tables dropped at the end. This is fast and isolated.
"""
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infrastructure.database.base import Base
from src.infrastructure.database.models import (
    ContentBlockModel,
    CourseModel,
    ModuleModel,
    TopicModel,
)


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Per-test in-memory async engine with schema created."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )
    _enable_sqlite_foreign_keys(eng)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield eng
    finally:
        async with eng.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the test engine."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A single async session for a test.

    The test owns the transaction. Use `await session.commit()` or
    `await session.rollback()` as needed.
    """
    async with session_factory() as session:
        yield session
