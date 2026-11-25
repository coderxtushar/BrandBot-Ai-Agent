"""Run the graph and translate its stream into simple (kind, payload) events."""

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

from backend.schemas import RunResult


def to_result(state: dict, order: Sequence[str]) -> RunResult:
    rank = {str(p): i for i, p in enumerate(order)}
    return RunResult(
        brand_profile=state["brand_profile"],
        plan=state["plan"],
        sources=state.get("sources", []),
        results=sorted(state.get("results", []), key=lambda r: rank.get(r.platform.value, 99)),
    )


async def graph_events(
    graph, graph_input: Any, *, order: Sequence[str], config: dict | None = None
) -> AsyncIterator[tuple[str, Any]]:
    """Yield ("progress", dict) events, then either ("final", RunResult) or ("interrupt", state).

    `graph_input` is the initial state, or a `Command(resume=...)` to continue a paused run.
    """
    final: dict | None = None
    async for ns, mode, chunk in graph.astream(
        graph_input, config, stream_mode=["custom", "values"], subgraphs=True
    ):
        if mode == "custom":
            yield "progress", chunk
        elif mode == "values" and not ns:
            final = chunk

    if config and getattr(graph, "checkpointer", None):
        snapshot = await graph.aget_state(config)
        if snapshot.interrupts:
            yield "interrupt", snapshot.values
            return
    if final is None or "plan" not in final:
        raise RuntimeError("Workflow produced no output")
    yield "final", to_result(final, order)


def sse(event: str, data: Any) -> dict:
    if hasattr(data, "model_dump_json"):
        return {"event": event, "data": data.model_dump_json()}
    return {"event": event, "data": json.dumps(data)}
