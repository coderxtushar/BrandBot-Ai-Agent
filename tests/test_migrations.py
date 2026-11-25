"""Alembic migrations must build the same schema as the ORM models."""

from alembic import command
from alembic.config import Config

from backend.config import get_settings


def test_migrations_match_models(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'mig.db'}")
    get_settings.cache_clear()
    try:
        cfg = Config("alembic.ini")
        command.upgrade(cfg, "head")
        command.check(cfg)  # raises if models have changes without a migration
        command.downgrade(cfg, "base")
    finally:
        get_settings.cache_clear()
