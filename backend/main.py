"""Brand Bot API.

Run:  uvicorn backend.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agents.checkpoint import open_checkpointer
from backend.api import brands, drafts, images, runs
from backend.config import get_settings
from backend.db.session import get_database
from backend.platforms import PLATFORMS
from backend.schemas import PlatformId

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = app.dependency_overrides.get(get_database, get_database)()
    if settings.db_auto_create:
        await db.create_all()
    checkpoints = app.dependency_overrides.get(open_checkpointer, open_checkpointer)
    async with checkpoints() as checkpointer:  # durable state for paused runs
        app.state.checkpointer = checkpointer
        yield
    await db.dispose()


app = FastAPI(
    title="Brand Bot API",
    description="Multi-platform personal branding agent: brand profile, research, and platform-native content.",
    version="0.5.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["*"],
)
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
