"""Central settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Providers ---
    google_api_key: str = Field(default="", description="Gemini API key")
    tavily_api_key: str = Field(default="", description="Tavily API key")

    # --- Models ---
    gemini_model: str = "gemini-3.5-flash"          # drafting / planning
    gemini_review_model: str = "gemini-3.5-flash"   # reviewing (swap to a Pro model for stricter review)
    temperature: float = 0.7

    # --- Agent behaviour ---
    max_revisions: int = Field(default=2, ge=0, le=5)  # review -> rewrite loops per platform
    search_results_per_query: int = Field(default=4, ge=1, le=10)
    search_depth: str = "basic"                       # "basic" | "advanced" (advanced costs 2 credits)

    # --- Database ---
    # SQLite works out of the box. For Postgres: postgresql+asyncpg://user:pass@host:5432/brandbot
    database_url: str = "sqlite+aiosqlite:///./brandbot.db"
    db_auto_create: bool = Field(
        default=True, description="Create tables on startup (dev). Use `alembic upgrade head` in production."
    )

    checkpoint_db: str = Field(
        default="brandbot_checkpoints.db",
        description="SQLite file for paused-run checkpoints (only used when DATABASE_URL is SQLite)",
    )

    # --- Dev ---
    demo_mode: bool = Field(default=False, description="Use canned AI output (no API keys or credits needed)")

    # --- API ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
