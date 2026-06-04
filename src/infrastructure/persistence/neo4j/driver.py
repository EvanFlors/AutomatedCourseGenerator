"""Async Neo4j driver factory.

Provides a single source of truth for the AsyncDriver instance used
across the application. Driver creation is lazy and cached.
"""
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from src.bootstrap.settings import Settings, get_settings


def create_driver(settings: Settings | None = None) -> AsyncDriver:
    settings = settings or get_settings()
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        _driver = create_driver()
    return _driver


def reset_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
    _driver = None


async def verify_connectivity(driver: AsyncDriver | None = None) -> dict[str, Any]:
    """Run a quick `RETURN 1` to verify the driver can talk to Neo4j.

    Returns the server info dictionary.
    """
    driver = driver or get_driver()
    async with driver.session() as session:
        result = await session.run("RETURN 1 AS n")
        record = await result.single()
        await result.consume()
        if record is None or record["n"] != 1:
            raise RuntimeError("Neo4j connectivity check failed.")
    summary = await driver.get_server_info()
    return {"address": summary.address}
