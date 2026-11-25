"""Stateless runs: generate without saving anything (handy for scripts and quick tests)."""

import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from backend.agents.graph import initial_state
from backend.api.deps import current_user, graph_dep
from backend.api.streaming import graph_events, sse
from backend.db.models import User
from backend.observability import trace_config
from backend.ratelimit import per_user
from backend.schemas import RunRequest, RunResult

# Stateless runs still spend AI credits, so they need a signed-in user too.
router = APIRouter(
    prefix="/runs",
    tags=["stateless runs"],
    dependencies=[Depends(current_user), per_user("runs", "rate_limit_runs", "AI runs")],
)
log = logging.getLogger("brandbot")


@router.post("", response_model=RunResult)
async def create_run(req: RunRequest, graph=Depends(graph_dep), user: User = Depends(current_user)):
    """Run the full workflow and return the final result (no streaming, not saved)."""
    config = trace_config("stateless run", user_id=user.id, platforms=req.platforms)
    async for kind, payload in graph_events(graph, initial_state(req), order=req.platforms, config=config):
        if kind == "final":
            return payload


@router.post("/stream")
async def stream_run(req: RunRequest, graph=Depends(graph_dep), user: User = Depends(current_user)):
    """Stream Server-Sent Events: `progress`*, then `result` (RunResult) or `error`. Not saved."""
    config = trace_config("stateless run", user_id=user.id, platforms=req.platforms)

    async def events():
        try:
            async for kind, payload in graph_events(graph, initial_state(req), order=req.platforms, config=config):
                yield sse("progress" if kind == "progress" else "result", payload)
        except Exception as exc:
            log.exception("Run failed")
            yield sse("error", {"detail": str(exc)})

    return EventSourceResponse(events())
