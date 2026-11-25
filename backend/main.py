"""Brand Bot API.

Run:  uvicorn backend.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.agents.checkpoint import open_checkpointer
from backend.api import auth, brands, connections, drafts, images, publications, runs
from backend.api.deps import clients_dep, storage_dep
from backend.config import get_settings
from backend.db.session import get_database
from backend.publishing.service import Publisher, Scheduler
from backend.security import get_cipher
from backend.platforms import PLATFORMS
from backend.schemas import PlatformId

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("brandbot")

settings = get_settings()
if settings.secret_key == "dev-secret-change-me" and not settings.demo_mode:
    log.warning("SECRET_KEY is the development default. Set a long random value before connecting real accounts.")


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
    version="0.6.0",
    lifespan=lifespan,
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
)
app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(publications.router)
app.include_router(brands.router)
app.include_router(drafts.router)
app.include_router(images.router)
app.include_router(runs.router)


class PlatformInfo(BaseModel):
    id: PlatformId
    label: str
    max_variants: int


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/platforms", response_model=list[PlatformInfo], tags=["meta"])
def list_platforms():
    return [PlatformInfo(id=s.id, label=s.label, max_variants=s.max_variants) for s in PLATFORMS.values()]
