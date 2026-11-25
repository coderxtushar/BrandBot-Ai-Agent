"""Stateless runs: generate without saving anything (handy for scripts and quick tests)."""

import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from backend.agents.graph import initial_state
from backend.api.deps import current_user, graph_dep
from backend.api.streaming import graph_events, sse
from backend.schemas import RunRequest, RunResult

# Stateless runs still spend AI credits, so they need a signed-in user too.
router = APIRouter(prefix="/runs", tags=["stateless runs"], dependencies=[Depends(current_user)])
log = logging.getLogger("brandbot")


@router.post("", response_model=RunResult)
async def create_run(req: RunRequest, graph=Depends(graph_dep)):
    """Run the full workflow and return the final result (no streaming, not saved)."""
    async for kind, payload in graph_events(graph, initial_state(req), order=req.platforms):
        if kind == "final":
            return payload


@router.post("/stream")
async def stream_run(req: RunRequest, graph=Depends(graph_dep)):
    """Stream Server-Sent Events: `progress`*, then `result` (RunResult) or `error`. Not saved."""

    async def events():
        try:
            async for kind, payload in graph_events(graph, initial_state(req), order=req.platforms):
                yield sse("progress" if kind == "progress" else "result", payload)
        except Exception as exc:
            log.exception("Run failed")
            yield sse("error", {"detail": str(exc)})

    return EventSourceResponse(events())
