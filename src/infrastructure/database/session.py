from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.bootstrap.settings import Settings, get_settings


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    settings = settings or get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        future=True,
        pool_pre_ping=True,
    )
    if _is_sqlite(settings.database_url):
        _enable_sqlite_foreign_keys(engine)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def reset_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.sync_engine.dispose()
    _engine = None
    _session_factory = None
