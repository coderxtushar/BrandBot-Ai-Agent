"""Brands, saved profiles, and run history."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import graph_dep
from backend.api.streaming import graph_events, sse
from backend.db import repo
from backend.db.models import Brand, Run
from backend.db.session import Database, get_database, get_session
from backend.schemas import (
    BrandCreate,
    BrandInput,
    BrandOut,
    BrandProfile,
    BrandRunRequest,
    BrandUpdate,
    RunDetail,
    RunRequest,
    RunSummary,
)

router = APIRouter(tags=["brands & history"])
log = logging.getLogger("brandbot")


async def _brand_or_404(brand_id: str, s: AsyncSession = Depends(get_session)) -> Brand:
    brand = await repo.get_brand(s, brand_id)
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


async def _run_or_404(run_id: str, s: AsyncSession = Depends(get_session)) -> Run:
    run = await repo.get_run(s, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------


@router.post("/brands", response_model=BrandOut, status_code=201)
async def create_brand(data: BrandCreate, s: AsyncSession = Depends(get_session)):
    return repo.brand_out(await repo.create_brand(s, data))


@router.get("/brands", response_model=list[BrandOut])
async def list_brands(s: AsyncSession = Depends(get_session)):
    return [repo.brand_out(b) for b in await repo.list_brands(s)]


@router.get("/brands/{brand_id}", response_model=BrandOut)
async def get_brand(brand: Brand = Depends(_brand_or_404)):
    return repo.brand_out(brand)


@router.patch("/brands/{brand_id}", response_model=BrandOut)
async def update_brand(data: BrandUpdate, brand: Brand = Depends(_brand_or_404), s: AsyncSession = Depends(get_session)):
    return repo.brand_out(await repo.update_brand(s, brand, data))


@router.put("/brands/{brand_id}/profile", response_model=BrandOut)
async def replace_profile(
    profile: BrandProfile, brand: Brand = Depends(_brand_or_404), s: AsyncSession = Depends(get_session)
):
    """Save a hand-edited brand profile. Future runs will use it."""
    return repo.brand_out(await repo.set_profile(s, brand, profile))


@router.delete("/brands/{brand_id}", status_code=204)
async def delete_brand(brand: Brand = Depends(_brand_or_404), s: AsyncSession = Depends(get_session)):
    await repo.delete_brand(s, brand)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Runs for a brand (saved)
# ---------------------------------------------------------------------------


def _run_request(brand: Brand, body: BrandRunRequest) -> RunRequest:
    return RunRequest(
        brand=BrandInput.model_validate(brand.input),
        platforms=body.platforms,
        topic=body.topic,
        variants=body.variants,
        brand_profile=None if body.regenerate_profile or not brand.profile else brand.profile,
    )


async def _fail(db: Database, run_id: str, error: str, status: str = "failed") -> None:
    async with db.sessions() as s:
        await repo.fail_run(s, run_id, error, status)


@router.post("/brands/{brand_id}/runs", response_model=RunDetail, status_code=201)
async def create_brand_run(
    body: BrandRunRequest,
    brand: Brand = Depends(_brand_or_404),
    s: AsyncSession = Depends(get_session),
    db: Database = Depends(get_database),
    graph=Depends(graph_dep),
):
    """Generate and save a run (no streaming)."""
    req = _run_request(brand, body)
    run = await repo.create_run(s, brand, body)
    try:
        async for kind, payload in graph_events(graph, req):
            if kind == "final":
                return repo.run_detail(await repo.complete_run(s, run.id, payload))
    except Exception as exc:
        log.exception("Run %s failed", run.id)
        await _fail(db, run.id, str(exc))
        raise HTTPException(status_code=502, detail=f"Workflow failed: {exc}") from exc


@router.post("/brands/{brand_id}/runs/stream")
async def stream_brand_run(
    body: BrandRunRequest,
    brand: Brand = Depends(_brand_or_404),
    s: AsyncSession = Depends(get_session),
    db: Database = Depends(get_database),
    graph=Depends(graph_dep),
):
    """Generate and save a run, streaming SSE: `run` (id), `progress`*, then `result` (RunDetail) or `error`."""
    req = _run_request(brand, body)
    run_id = (await repo.create_run(s, brand, body)).id

    async def events():
        yield sse("run", {"run_id": run_id})
        try:
            async for kind, payload in graph_events(graph, req):
                if kind == "progress":
                    yield sse("progress", payload)
                    continue
                async with db.sessions() as session:
                    detail = repo.run_detail(await repo.complete_run(session, run_id, payload))
                yield sse("result", detail)
        except asyncio.CancelledError:  # client disconnected / pressed Stop
            await asyncio.shield(_fail(db, run_id, "Cancelled", "cancelled"))
            raise
        except Exception as exc:
            log.exception("Run %s failed", run_id)
            await _fail(db, run_id, str(exc))
            yield sse("error", {"detail": str(exc), "run_id": run_id})

    return EventSourceResponse(events())


@router.get("/brands/{brand_id}/runs", response_model=list[RunSummary])
async def list_brand_runs(
    brand: Brand = Depends(_brand_or_404),
    s: AsyncSession = Depends(get_session),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return [repo.run_summary(r) for r in await repo.list_runs(s, brand.id, limit, offset)]


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run: Run = Depends(_run_or_404)):
    return repo.run_detail(run)


@router.delete("/runs/{run_id}", status_code=204)
async def delete_run(run: Run = Depends(_run_or_404), s: AsyncSession = Depends(get_session)):
    await repo.delete_run(s, run)
    return Response(status_code=204)
