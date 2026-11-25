"""Durable LangGraph checkpoints, so a paused run (waiting for the user) survives restarts.

- SQLite database  -> checkpoints in a separate SQLite file (settings.checkpoint_db)
- Postgres database -> checkpoints in the same Postgres database (LangGraph creates its own tables)
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
    """SQLAlchemy URL (postgresql+asyncpg://...?ssl=require) -> libpq DSN (postgresql://...?sslmode=require)."""
    parts = urlsplit("postgresql://" + url.split("://", 1)[1])
    query = [("sslmode" if k == "ssl" else k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit(parts._replace(query=urlencode(query)))


@asynccontextmanager
async def open_checkpointer(settings: Settings | None = None) -> AsyncIterator:
    settings = settings or get_settings()
    serde = make_serde()
    if settings.database_url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        # A pool, not one long-lived connection: serverless Postgres (Neon) drops connections when it sleeps and
        # databases restart. check_connection replaces a dead connection before it's handed out.
        pool = AsyncConnectionPool(
            _postgres_dsn(settings.database_url),
            min_size=1,
            max_size=5,
            open=False,
            check=AsyncConnectionPool.check_connection,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        async with pool:
            saver = AsyncPostgresSaver(conn=pool, serde=serde)
            await saver.setup()
            yield saver
    else:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        async with aiosqlite.connect(settings.checkpoint_db) as conn:
            saver = AsyncSqliteSaver(conn, serde=serde)
            await saver.setup()
            yield saver
