"""Brand Bot API.

Run:  uvicorn backend.main:app --reload
"""

import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.agents.graph import build_graph, initial_state
from backend.config import get_settings
from backend.platforms import PLATFORMS
from backend.schemas import PlatformId, RunRequest, RunResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("brandbot")

settings = get_settings()

app = FastAPI(
    title="Brand Bot API",
    description="Multi-platform personal branding agent: brand profile, research, and platform-native content.",
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache
def get_graph():
    """Build the real graph once (overridden in tests)."""
    s = get_settings()
    if s.demo_mode:
        from backend.services.fakes import FakeLLM, FakeSearcher

        log.warning("DEMO_MODE is on: returning canned content, no AI calls are made.")
        return build_graph(FakeLLM(reject_first_review=True, delay=0.6), FakeSearcher(delay=0.8), max_revisions=s.max_revisions)

    from backend.services.llm import GeminiClient
    from backend.services.search import TavilySearcher

    return build_graph(GeminiClient(s), TavilySearcher(s), max_revisions=s.max_revisions)


def _graph_dep():
    try:
        return get_graph()
    except RuntimeError as exc:  # missing API keys
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _to_result(state: dict, req: RunRequest) -> RunResult:
    order = {p: i for i, p in enumerate(req.platforms)}
    return RunResult(
        brand_profile=state["brand_profile"],
        plan=state["plan"],
        sources=state.get("sources", []),
        results=sorted(state.get("results", []), key=lambda r: order.get(r.platform, 99)),
    )


class PlatformInfo(BaseModel):
    id: PlatformId
    label: str
    max_variants: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/platforms", response_model=list[PlatformInfo])
def list_platforms():
    return [PlatformInfo(id=s.id, label=s.label, max_variants=s.max_variants) for s in PLATFORMS.values()]


@app.post("/runs", response_model=RunResult)
async def create_run(req: RunRequest, graph=Depends(_graph_dep)):
    """Run the full workflow and return the final result (no streaming)."""
    state = await graph.ainvoke(initial_state(req))
    return _to_result(state, req)


@app.post("/runs/stream")
async def stream_run(req: RunRequest, graph=Depends(_graph_dep)):
    """Run the workflow, streaming Server-Sent Events.

    Events:
      progress -> {"stage": ..., "platform"?: ..., ...}
      result   -> RunResult JSON
      error    -> {"detail": "..."}
    """

    async def events() -> AsyncIterator[dict]:
        final: dict | None = None
        try:
            async for ns, mode, chunk in graph.astream(
                initial_state(req), stream_mode=["custom", "values"], subgraphs=True
            ):
                if mode == "custom":
                    yield {"event": "progress", "data": json.dumps(chunk)}
                elif mode == "values" and not ns:
                    final = chunk
            if final is None:
                raise RuntimeError("Workflow produced no output")
            yield {"event": "result", "data": _to_result(final, req).model_dump_json()}
        except Exception as exc:
            log.exception("Run failed")
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}

    return EventSourceResponse(events())
