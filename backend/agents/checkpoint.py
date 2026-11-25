"""Durable LangGraph checkpoints, so a paused run (waiting for the user) survives restarts.

- SQLite database  -> checkpoints in a separate SQLite file (settings.checkpoint_db)
- Postgres database -> checkpoints in the same Postgres database (LangGraph creates its own tables)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from backend import schemas
from backend.config import Settings, get_settings

# Types stored in graph state. LangGraph only deserialises types it has been told about.
_STATE_TYPES = [
    "PlatformId", "BrandInput", "BrandProfile", "VoiceGuide", "ContentPlan", "SearchQuery",
    "Source", "PlatformResult", "Review",
]


def make_serde() -> JsonPlusSerializer:
    for name in _STATE_TYPES:  # fail fast if a schema is renamed
        getattr(schemas, name)
    return JsonPlusSerializer(allowed_msgpack_modules=[("backend.schemas", n) for n in _STATE_TYPES])


def _postgres_dsn(url: str) -> str:
    """SQLAlchemy URL (postgresql+asyncpg://...) -> libpq DSN (postgresql://...)."""
    return "postgresql://" + url.split("://", 1)[1]


@asynccontextmanager
async def open_checkpointer(settings: Settings | None = None) -> AsyncIterator:
    settings = settings or get_settings()
    serde = make_serde()
    if settings.database_url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(_postgres_dsn(settings.database_url), serde=serde) as saver:
            await saver.setup()
            yield saver
    else:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with aiosqlite.connect(settings.checkpoint_db) as conn:
            saver = AsyncSqliteSaver(conn, serde=serde)
            await saver.setup()
            yield saver
