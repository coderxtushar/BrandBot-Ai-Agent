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
    gemini_image_model: str = "gemini-3.1-flash-image"  # image generation
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

    # --- Media ---
    media_dir: str = Field(default="media", description="Where generated images are stored")

    # --- Accounts & security ---
    secret_key: str = Field(
        default="dev-secret-change-me",
        description="Encrypts platform tokens at rest. Set a long random value in production.",
    )
    session_days: int = 30
    cookie_secure: bool = Field(default=False, description="Send cookies over HTTPS only (turn on in production)")

    # --- Public URLs ---
    api_public_url: str = Field(
        default="http://localhost:8000",
        description="Where this API is reachable. Used for OAuth callbacks and image URLs that platforms fetch.",
    )
    web_url: str = Field(default="http://localhost:3000", description="The web app, for redirects after connecting")

    # --- Publishing ---
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = Field(default=30, ge=5)
    metrics_refresh_hours: float = Field(default=6, gt=0, description="How often to re-read stats of recent posts")
    metrics_max_age_days: int = Field(default=30, ge=1, description="Stop tracking stats this long after publishing")
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_api_version: str = Field(default="202607", description="LinkedIn-Version header (YYYYMM)")
    x_client_id: str = ""
    x_client_secret: str = ""
    threads_app_id: str = ""
    threads_app_secret: str = ""
    instagram_app_id: str = ""
    instagram_app_secret: str = ""

    # --- Dev ---
    demo_mode: bool = Field(default=False, description="Use canned AI output (no API keys or credits needed)")

    # --- API ---
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]  # Next.js dev server


@lru_cache
def get_settings() -> Settings:
    return Settings()
