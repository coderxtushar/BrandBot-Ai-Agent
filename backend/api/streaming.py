"""Run the graph and translate its stream into simple (kind, payload) events."""

import json
from collections.abc import AsyncIterator
from typing import Any

from backend.agents.graph import initial_state
from backend.schemas import RunRequest, RunResult


def to_result(state: dict, req: RunRequest) -> RunResult:
    order = {p: i for i, p in enumerate(req.platforms)}
    return RunResult(
        brand_profile=state["brand_profile"],
        plan=state["plan"],
        sources=state.get("sources", []),
        results=sorted(state.get("results", []), key=lambda r: order.get(r.platform, 99)),
    )


async def graph_events(graph, req: RunRequest) -> AsyncIterator[tuple[str, Any]]:
    """Yield ("progress", dict) for each progress event, then ("final", RunResult)."""
    final: dict | None = None
    async for ns, mode, chunk in graph.astream(initial_state(req), stream_mode=["custom", "values"], subgraphs=True):
        if mode == "custom":
            yield "progress", chunk
        elif mode == "values" and not ns:
            final = chunk
    if final is None:
        raise RuntimeError("Workflow produced no output")
    yield "final", to_result(final, req)


def sse(event: str, data: Any) -> dict:
    if hasattr(data, "model_dump_json"):
        return {"event": event, "data": data.model_dump_json()}
    return {"event": event, "data": json.dumps(data)}
