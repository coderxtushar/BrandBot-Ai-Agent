"""Brands, saved profiles, and run history."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.agents.graph import initial_state
from backend.api.deps import current_user, durable_graph_dep, storage_dep
from backend.db import accounts as acc
from backend.api.streaming import graph_events, sse
from backend.db import repo
from backend.db.models import Brand, Run, User
from backend.db.performance import brand_performance
from backend.db.session import Database, get_database, get_session
from backend.observability import trace_config
from backend.ratelimit import per_user
from backend.schemas import (
    BrandCreate,
    BrandInput,
    BrandOut,
    BrandProfile,
    BrandRunRequest,
    BrandUpdate,
    PlanDecision,
    RunDetail,
    RunRequest,
    RunSummary,
)

router = APIRouter(tags=["brands & history"])
RUN_LIMIT = per_user("runs", "rate_limit_runs", "AI runs")
log = logging.getLogger("brandbot")


async def _brand_or_404(
    brand_id: str, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> Brand:
    brand = await repo.get_brand(s, brand_id)
    if brand is None or brand.user_id != user.id:  # someone else's brand looks exactly like a missing one
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


async def _run_or_404(run_id: str, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)) -> Run:
    run = await repo.get_run(s, run_id)
    owner = await s.get(Brand, run.brand_id) if run else None
    if run is None or owner is None or owner.user_id != user.id:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------


@router.post("/brands", response_model=BrandOut, status_code=201)
async def create_brand(data: BrandCreate, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)):
    return repo.brand_out(await repo.create_brand(s, data, user.id))


@router.get("/brands", response_model=list[BrandOut])
async def list_brands(s: AsyncSession = Depends(get_session), user: User = Depends(current_user)):
    return [repo.brand_out(b) for b in await repo.list_brands(s, user.id)]


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
async def delete_brand(
    brand: Brand = Depends(_brand_or_404), s: AsyncSession = Depends(get_session), storage=Depends(storage_dep)
):
    keys = await repo.media_keys(s, brand_id=brand.id) + await acc.publication_keys(s, brand_id=brand.id)
    await repo.delete_brand(s, brand)
    for key in keys:  # files go after the rows are gone
        await storage.delete(key)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Runs for a brand (saved, checkpointed)
# ---------------------------------------------------------------------------


def _run_request(brand: Brand, body: BrandRunRequest) -> RunRequest:
    return RunRequest(
        brand=BrandInput.model_validate(brand.input),
        platforms=body.platforms,
        topic=body.topic,
        variants=body.variants,
        brand_profile=None if body.regenerate_profile or not brand.profile else brand.profile,
    )


def _thread(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _run_config(run_id: str, user_id: str, brand_id: str, platforms, name: str) -> dict:
    """Checkpoint thread + LangSmith name, tags and ids for this run."""
    return {**trace_config(name, user_id=user_id, brand_id=brand_id, run_id=run_id, platforms=platforms), **_thread(run_id)}


async def _fail(db: Database, run_id: str, error: str, status: str = "failed") -> None:
    async with db.sessions() as s:
        await repo.fail_run(s, run_id, error, status)


async def _forget(graph, run_id: str) -> None:
    """Drop a finished run's checkpoints; the result lives in our own tables."""
    try:
        await graph.checkpointer.adelete_thread(run_id)
    except Exception:  # best effort
        log.warning("Could not delete checkpoints for run %s", run_id, exc_info=True)


async def _drive(graph, db: Database, run_id: str, graph_input, order, config: dict) -> object:
    """Run (or resume) the graph, persist the outcome, and yield SSE events."""
    try:
        async for kind, payload in graph_events(graph, graph_input, order=order, config=config):
            if kind == "progress":
                yield sse("progress", payload)
            elif kind == "interrupt":
                async with db.sessions() as session:
                    detail = repo.run_detail(await repo.mark_awaiting(session, run_id, payload))
                yield sse("awaiting", detail)
            else:
                async with db.sessions() as session:
                    detail = repo.run_detail(await repo.complete_run(session, run_id, payload))
                await _forget(graph, run_id)
                yield sse("result", detail)
    except asyncio.CancelledError:  # client disconnected / pressed Stop
        await asyncio.shield(_fail(db, run_id, "Cancelled", "cancelled"))
        raise
    except Exception as exc:
        log.exception("Run %s failed", run_id)
        await _fail(db, run_id, str(exc))
        yield sse("error", {"detail": str(exc), "run_id": run_id})


@router.post("/brands/{brand_id}/runs", response_model=RunDetail, status_code=201, dependencies=[RUN_LIMIT])
async def create_brand_run(
    body: BrandRunRequest,
    brand: Brand = Depends(_brand_or_404),
    s: AsyncSession = Depends(get_session),
    db: Database = Depends(get_database),
    graph=Depends(durable_graph_dep),
):
    """Generate and save a run (no streaming). With review_plan it returns paused (status awaiting_plan)."""
    req = _run_request(brand, body)
    performance = await brand_performance(s, brand.id, [p.value for p in req.platforms]) if body.learn_from_results else None
    run_id = (await repo.create_run(s, brand, body)).id
    try:
        async for kind, payload in graph_events(
            graph,
            initial_state(req, body.review_plan, performance),
            order=req.platforms,
            config=_run_config(run_id, brand.user_id, brand.id, req.platforms, "brand run"),
        ):
            if kind == "interrupt":
                return repo.run_detail(await repo.mark_awaiting(s, run_id, payload))
            if kind == "final":
                detail = repo.run_detail(await repo.complete_run(s, run_id, payload))
                await _forget(graph, run_id)
                return detail
    except Exception as exc:
        log.exception("Run %s failed", run_id)
        await _fail(db, run_id, str(exc))
        raise HTTPException(status_code=502, detail=f"Workflow failed: {exc}") from exc


@router.post("/brands/{brand_id}/runs/stream", dependencies=[RUN_LIMIT])
async def stream_brand_run(
    body: BrandRunRequest,
    brand: Brand = Depends(_brand_or_404),
    s: AsyncSession = Depends(get_session),
    db: Database = Depends(get_database),
    graph=Depends(durable_graph_dep),
):
    """Generate and save a run, streaming SSE.

    Events: `run` (id), `progress`*, then one of `result` (RunDetail), `awaiting` (RunDetail paused
    for plan review; continue with POST /runs/{id}/resume/stream), or `error`.
    """
    req = _run_request(brand, body)
    performance = await brand_performance(s, brand.id, [p.value for p in req.platforms]) if body.learn_from_results else None
    run_id = (await repo.create_run(s, brand, body)).id

    config = _run_config(run_id, brand.user_id, brand.id, req.platforms, "brand run")

    async def events():
        yield sse("run", {"run_id": run_id})
        if performance:
            yield sse("progress", {"stage": "learning", "status": "done", "platforms": sorted(performance["examples"])})
        async for event in _drive(graph, db, run_id, initial_state(req, body.review_plan, performance), req.platforms, config):
            yield event

    return EventSourceResponse(events())


async def _awaiting_run(run: Run, graph, s: AsyncSession) -> Run:
    if run.status != "awaiting_plan":
        raise HTTPException(status_code=409, detail=f"Run is {run.status}, not waiting for review")
    snapshot = await graph.aget_state(_thread(run.id))
    if not snapshot.interrupts:
        await repo.fail_run(s, run.id, "Saved progress for this run was lost; start a new run.")
        raise HTTPException(status_code=409, detail="This run can no longer be resumed; start a new run.")
    return run


@router.post("/runs/{run_id}/resume/stream", dependencies=[RUN_LIMIT])
async def resume_run(
    decision: PlanDecision,
    run: Run = Depends(_run_or_404),
    s: AsyncSession = Depends(get_session),
    db: Database = Depends(get_database),
    graph=Depends(durable_graph_dep),
    user: User = Depends(current_user),
):
    """Continue a run paused for plan review with the author's (optionally edited) angle and sources."""
    await _awaiting_run(run, graph, s)
    await repo.mark_running(s, run)
    run_id, order = run.id, list(run.platforms)
    config = _run_config(run_id, user.id, run.brand_id, order, "brand run (resumed)")

    async def events():
        yield sse("run", {"run_id": run_id})
        async for event in _drive(graph, db, run_id, Command(resume=decision.model_dump()), order, config):
            yield event

    return EventSourceResponse(events())


@router.post("/runs/{run_id}/cancel", response_model=RunDetail)
async def cancel_run(run: Run = Depends(_run_or_404), s: AsyncSession = Depends(get_session), graph=Depends(durable_graph_dep)):
    """Abandon a run that is waiting for plan review."""
    if run.status != "awaiting_plan":
        raise HTTPException(status_code=409, detail=f"Run is {run.status}; only paused runs can be cancelled")
    await repo.fail_run(s, run.id, "Cancelled during plan review", "cancelled")
    await _forget(graph, run.id)
    return repo.run_detail(await repo.get_run(s, run.id))


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
async def delete_run(
    request: Request,
    run: Run = Depends(_run_or_404),
    s: AsyncSession = Depends(get_session),
    storage=Depends(storage_dep),
):
    if run.status == "awaiting_plan":  # drop its saved checkpoints too
        await _forget_on_app(request, run.id)
    keys = await repo.media_keys(s, run_id=run.id) + await acc.publication_keys(s, run_id=run.id)
    await repo.delete_run(s, run)
    for key in keys:
        await storage.delete(key)
    return Response(status_code=204)


async def _forget_on_app(request: Request, run_id: str) -> None:
    checkpointer = getattr(request.app.state, "checkpointer", None)
    if checkpointer is not None:
        try:
            await checkpointer.adelete_thread(run_id)
        except Exception:
            log.warning("Could not delete checkpoints for run %s", run_id, exc_info=True)
