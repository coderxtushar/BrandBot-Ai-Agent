"""Engine and session management."""

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.db.models import Base


def _enable_sqlite_fks(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


class Database:
    def __init__(self, url: str):
        kwargs = {} if url.startswith("sqlite") else {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}
        self.engine = create_async_engine(url, **kwargs)
        if url.startswith("sqlite"):
            # SQLite ignores ON DELETE CASCADE unless foreign keys are enabled per connection.
            event.listen(self.engine.sync_engine, "connect", _enable_sqlite_fks)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()


@lru_cache
def get_database() -> Database:
    return Database(get_settings().database_url)


async def get_session(db: Database = Depends(get_database)) -> AsyncIterator[AsyncSession]:
    async with db.sessions() as session:
        yield session
