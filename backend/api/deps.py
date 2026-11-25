"""Shared FastAPI dependencies: AI services and the graphs built from them."""

import logging
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, HTTPException, Request

from backend.agents.graph import build_graph, build_platform_graph
from backend.config import get_settings

log = logging.getLogger("brandbot")


@dataclass(frozen=True, eq=False)
class Services:
    llm: object
    searcher: object
    max_revisions: int
    images: object = None  # ImageGenerator


@lru_cache
def get_services() -> Services:
    """Real Gemini + Tavily clients (or canned fakes in DEMO_MODE), created once per process."""
    s = get_settings()
    if s.demo_mode:
        from backend.services.fakes import FakeLLM, FakeSearcher
        from backend.services.images import FakeImageGenerator

        log.warning("DEMO_MODE is on: returning canned content, no AI calls are made.")
        return Services(
            FakeLLM(reject_first_review=True, delay=0.6),
            FakeSearcher(delay=0.8),
            s.max_revisions,
            FakeImageGenerator(delay=1.2),
        )

    from backend.services.images import GeminiImageGenerator
    from backend.services.llm import GeminiClient
    from backend.services.search import TavilySearcher

    return Services(GeminiClient(s), TavilySearcher(s), s.max_revisions, GeminiImageGenerator(s))


@lru_cache
def get_storage():
    from backend.services.storage import LocalMediaStorage

    return LocalMediaStorage(get_settings().media_dir)


def storage_dep():
    return get_storage()


def services_dep() -> Services:
    try:
        return get_services()
    except RuntimeError as exc:  # missing API keys
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# Compiled graphs are cheap to keep and costly-ish to rebuild: cache per (kind, services, checkpointer).
_graphs: dict[tuple, object] = {}


def _cached(key: tuple, factory):
    if key not in _graphs:
        _graphs[key] = factory()
    return _graphs[key]


def graph_dep(services: Services = Depends(services_dep)):
    """Stateless graph: no checkpoints, can't pause."""
    return _cached(
        ("stateless", services),
        lambda: build_graph(services.llm, services.searcher, max_revisions=services.max_revisions),
    )


def durable_graph_dep(request: Request, services: Services = Depends(services_dep)):
    """Checkpointed graph: runs can pause for the author (plan review) and resume later."""
    checkpointer = request.app.state.checkpointer
    return _cached(
        ("durable", services, checkpointer),
        lambda: build_graph(
            services.llm, services.searcher, max_revisions=services.max_revisions, checkpointer=checkpointer
        ),
    )


def platform_graph_dep(services: Services = Depends(services_dep)):
    """The per-platform write -> review loop, used to rewrite a single draft."""
    return _cached(("platform", services), lambda: build_platform_graph(services.llm, services.max_revisions))
