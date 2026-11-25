"""Central settings, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-secret-change-me"


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
    media_backend: Literal["local", "gcs"] = Field(
        default="local", description="local disk (MEDIA_DIR) or a Google Cloud Storage bucket (GCS_BUCKET)"
    )
    media_dir: str = Field(default="media", description="Where generated images are stored (local backend)")
    gcs_bucket: str = Field(default="", description="Bucket for generated images (gcs backend)")

    # --- Accounts & security ---
    secret_key: str = Field(
        default=DEV_SECRET,
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

    cron_secret: str = Field(
        default="",
        description="Bearer token for POST /internal/tick, called every minute by Cloud Scheduler (or any cron)",
    )

    # --- Rate limits ("count/period", comma separated; period = second, minute, hour, day, e.g. "10/hour,40/day") ---
    rate_limits_enabled: bool = True
    rate_limit_runs: str = "10/hour,40/day"        # new AI runs and resumed runs, per user
    rate_limit_rewrites: str = "40/hour,200/day"   # AI rewrites of a single draft, per user
    rate_limit_images: str = "20/hour,60/day"      # generated images, per user
    rate_limit_login: str = "10/5minutes"          # sign-in attempts, per IP + email
    rate_limit_signup: str = "5/hour"              # new accounts, per IP

    # --- Tracing (LangSmith) ---
    langsmith_tracing: bool = Field(default=False, description="Send a trace of every AI run to LangSmith")
    langsmith_api_key: str = ""
    langsmith_project: str = "brand-bot"
    langsmith_endpoint: str = Field(default="", description="Only for non-default regions, e.g. https://eu.api.smith.langchain.com")

    # --- Deployment ---
    environment: Literal["development", "production"] = Field(
        default="development", description="production refuses to start with unsafe settings"
    )
    log_format: Literal["text", "json"] = Field(default="text", description="json for Cloud Logging and other collectors")
    trusted_proxy_hops: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Proxies in front of the API that append to X-Forwarded-For (Cloud Run: 1; Vercel -> Cloud Run: 2)",
    )
    google_cloud_project: str = Field(default="", description="Links JSON logs to Cloud Trace when set")

    # --- Dev ---
    demo_mode: bool = Field(default=False, description="Use canned AI output (no API keys or credits needed)")

    # --- API ---
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]  # Next.js dev server

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def deployment_problems(self) -> tuple[list[str], list[str]]:
        """(errors, warnings) for a production deployment. Errors stop the API from starting."""
        errors: list[str] = []
        warnings: list[str] = []
        if self.secret_key == DEV_SECRET or len(self.secret_key) < 32:
            errors.append("SECRET_KEY must be a random value of at least 32 characters.")
        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true (sessions over HTTPS only).")
        if self.demo_mode:
            errors.append("DEMO_MODE must be off.")
        if self.database_url.startswith("sqlite"):
            warnings.append("DATABASE_URL is SQLite; use Postgres when the disk isn't permanent (Cloud Run).")
        if self.media_backend == "local":
            warnings.append("MEDIA_BACKEND is local; images are lost when the container is replaced unless MEDIA_DIR is a volume.")
        if not self.scheduler_enabled and not self.cron_secret:
            warnings.append("The scheduler is off and CRON_SECRET is empty, so scheduled posts will never go out.")
        if any(h in self.api_public_url for h in ("localhost", "127.0.0.1")):
            warnings.append("API_PUBLIC_URL points to localhost; OAuth callbacks and Instagram/Threads images won't work.")
        if self.web_url.rstrip("/") not in [o.rstrip("/") for o in self.cors_origins]:
            warnings.append("WEB_URL isn't in CORS_ORIGINS; the web app's requests will be refused.")
        return errors, warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
