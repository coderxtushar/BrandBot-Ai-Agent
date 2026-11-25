"""Brand Bot API.

Run:  uvicorn backend.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from backend.agents.checkpoint import open_checkpointer
from backend.api import analytics, auth, brands, connections, drafts, images, internal, publications, runs
from backend.api.deps import clients_dep, storage_dep
from backend.config import DEV_SECRET, get_settings
from backend.db.session import Database, get_database
from backend.observability import RequestContextMiddleware, configure_tracing, setup_logging
from backend.publishing.service import Publisher, Scheduler
from backend.ratelimit import parse_rules
from backend.security import get_cipher
from backend.platforms import PLATFORMS
from backend.schemas import PlatformId

settings = get_settings()
setup_logging(settings)
log = logging.getLogger("brandbot")


def check_deployment() -> None:
    """Production refuses unsafe settings; development only warns about the secret."""
    for name in ("rate_limit_runs", "rate_limit_rewrites", "rate_limit_images", "rate_limit_login", "rate_limit_signup"):
        parse_rules(getattr(settings, name))  # a typo in a limit should stop startup, not the first request
    errors, warnings = settings.deployment_problems()
    if not settings.is_production:
        if settings.secret_key == DEV_SECRET and not settings.demo_mode:
            log.warning("SECRET_KEY is the development default. Set a long random value before connecting real accounts.")
        return
    for w in warnings:
        log.warning("Deployment: %s", w)
    if errors:
        raise RuntimeError("Unsafe production settings:\n- " + "\n- ".join(errors))


check_deployment()
if configure_tracing(settings):
    log.info("LangSmith tracing is on (project %s).", settings.langsmith_project)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = app.dependency_overrides.get(get_database, get_database)()
    if settings.db_auto_create:
        await db.create_all()
    override = app.dependency_overrides.get
    app.state.publisher = Publisher(db, override(clients_dep, clients_dep)(), override(storage_dep, storage_dep)(), get_cipher(), settings)
    scheduler = Scheduler(app.state.publisher, settings.scheduler_interval_seconds)
    if settings.scheduler_enabled:
        scheduler.start()
    checkpoints = override(open_checkpointer, open_checkpointer)
    async with checkpoints() as checkpointer:  # durable state for paused runs
        app.state.checkpointer = checkpointer
        yield
    await scheduler.stop()
    await db.dispose()


app = FastAPI(
    title="Brand Bot API",
    description="Multi-platform personal branding agent: brand profile, research, and platform-native content.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
)


@app.middleware("http")
async def reject_foreign_origins(request: Request, call_next):
    """CSRF guard: browsers send Origin on cross-site requests. State changes only from our own web app."""
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in settings.cors_origins:
        return JSONResponse({"detail": "Requests from this site aren't allowed."}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # the session cookie
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)  # outermost: every log line, including CORS rejections, has an id
app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(publications.router)
app.include_router(analytics.router)
app.include_router(brands.router)
app.include_router(drafts.router)
app.include_router(images.router)
app.include_router(runs.router)
app.include_router(internal.router)


class PlatformInfo(BaseModel):
    id: PlatformId
    label: str
    max_variants: int


@app.get("/health", tags=["meta"])
def health():
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/ready", tags=["meta"])
async def ready(db: Database = Depends(get_database)):
    """Readiness: the database answers. Point load balancers and uptime checks here."""
    try:
        async with db.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        log.exception("Readiness check failed")
        return JSONResponse({"status": "unavailable", "database": "unreachable"}, status_code=503)
    return {"status": "ok", "database": "ok"}


@app.get("/platforms", response_model=list[PlatformInfo], tags=["meta"])
def list_platforms():
    return [PlatformInfo(id=s.id, label=s.label, max_variants=s.max_variants) for s in PLATFORMS.values()]
