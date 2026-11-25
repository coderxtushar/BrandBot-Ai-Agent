"""Shared FastAPI dependencies."""

import logging
from functools import lru_cache

from fastapi import HTTPException

from backend.agents.graph import build_graph
from backend.config import get_settings

log = logging.getLogger("brandbot")


@lru_cache
def get_graph():
    """Build the agent graph once per process."""
    s = get_settings()
    if s.demo_mode:
        from backend.services.fakes import FakeLLM, FakeSearcher

        log.warning("DEMO_MODE is on: returning canned content, no AI calls are made.")
        return build_graph(
            FakeLLM(reject_first_review=True, delay=0.6), FakeSearcher(delay=0.8), max_revisions=s.max_revisions
        )

    from backend.services.llm import GeminiClient
    from backend.services.search import TavilySearcher

    return build_graph(GeminiClient(s), TavilySearcher(s), max_revisions=s.max_revisions)


def graph_dep():
    try:
        return get_graph()
    except RuntimeError as exc:  # missing API keys
        raise HTTPException(status_code=503, detail=str(exc)) from exc
