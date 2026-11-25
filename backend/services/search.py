"""Web research behind a tiny interface so the graph can be tested with a fake."""

import asyncio
import logging
from typing import Protocol

from backend.config import Settings
from backend.schemas import SearchQuery, Source

log = logging.getLogger(__name__)


class Searcher(Protocol):
    async def search(self, query: SearchQuery) -> list[Source]: ...


class TavilySearcher:
    def __init__(self, settings: Settings):
        from langchain_tavily import TavilySearch

        if not settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is not set. Add it to your .env file.")
        self._tool = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=settings.search_results_per_query,
            search_depth=settings.search_depth,
        )

    async def search(self, query: SearchQuery) -> list[Source]:
        args = {"query": query.query, "topic": query.topic}
        if query.time_range:
            args["time_range"] = query.time_range
        try:
            raw = await self._tool.ainvoke(args)
        except Exception as exc:  # no results / network error: research is best-effort
            log.warning("Search failed for %r: %s", query.query, exc)
            return []
        if not isinstance(raw, dict) or "error" in raw:
            log.warning("Search error for %r: %s", query.query, raw)
            return []
        return [
            Source(title=r.get("title", ""), url=r.get("url", ""), snippet=(r.get("content") or "")[:800])
            for r in raw.get("results", [])
            if r.get("url")
        ]


async def search_all(searcher: Searcher, queries: list[SearchQuery]) -> list[Source]:
    """Run queries concurrently and de-duplicate by URL."""
    batches = await asyncio.gather(*(searcher.search(q) for q in queries))
    seen, out = set(), []
    for batch in batches:
        for s in batch:
            if s.url not in seen:
                seen.add(s.url)
                out.append(s)
    return out
