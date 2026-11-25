"""The Brand Bot agent graph.

    START
      │
      ▼
   profile ──► planner ──► research ──┬── Send ─► platform[linkedin] ─┐
   (skipped if a                      ├── Send ─► platform[x]        ─┼──► END
    profile is supplied)              └── Send ─► platform[...]      ─┘

Each `platform` branch is its own subgraph that runs in parallel:

    write ──► review ──► approved / out of attempts? ──► finalize
      ▲                      │ no
      └──────────────────────┘   (lint issues + reviewer feedback sent back to the writer)
"""

import logging
import operator
from typing import Annotated, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from backend.agents import prompts
from backend.platforms import get_spec
from backend.schemas import (
    BrandInput,
    BrandProfile,
    ContentPlan,
    PlatformId,
    PlatformResult,
    Review,
    Source,
)
from backend.services.llm import LLMClient
from backend.services.search import Searcher, search_all

log = logging.getLogger(__name__)


def _emit(event: dict) -> None:
    """Send a progress event to anyone streaming with stream_mode='custom'."""
    try:
        get_stream_writer()(event)
    except Exception:  # not streaming / outside a runnable context
        pass


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class RunState(TypedDict, total=False):
    brand: BrandInput
    platforms: list[PlatformId]
    topic: str
    variants: int
    brand_profile: BrandProfile | None
    plan: ContentPlan
    sources: list[Source]
    results: Annotated[list[PlatformResult], operator.add]


class PlatformState(TypedDict, total=False):
    # inputs (from Send)
    platform: PlatformId
    brand_profile: BrandProfile
    plan: ContentPlan
    sources: list[Source]
    variants: int
    past_posts: str
    # working state
    drafts: list[dict]
    lint_issues: list[str]
    review: Review | None
    attempts: int
    error: str | None
    # output
    results: Annotated[list[PlatformResult], operator.add]


class PlatformOutput(TypedDict):
    results: Annotated[list[PlatformResult], operator.add]


# ---------------------------------------------------------------------------
# Per-platform subgraph
# ---------------------------------------------------------------------------

def build_platform_graph(llm: LLMClient, max_revisions: int):
    async def write(state: PlatformState):
        spec = get_spec(state["platform"])
        attempt = state.get("attempts", 0) + 1
        is_revision = attempt > 1
        _emit({"stage": "revising" if is_revision else "writing", "platform": spec.id.value, "attempt": attempt})

        variants = min(state.get("variants", 1), spec.max_variants)
        system, user = prompts.writer_prompts(
            spec,
            state["brand_profile"],
            state["plan"],
            state.get("sources", []),
            variants,
            state.get("past_posts", ""),
            previous={"items": state["drafts"]} if is_revision else None,
            feedback=prompts.merge_feedback(state.get("lint_issues", []), state.get("review")),
        )
        try:
            out = await llm.structured(spec.drafts_model, system, user, role="writer")
        except Exception as exc:
            log.exception("Writer failed for %s", spec.id)
            if is_revision:  # keep the previous draft rather than losing everything
                return {"attempts": attempt}
            return {"attempts": attempt, "error": f"Writer failed: {exc}"}
        drafts = [item.model_dump() for item in out.items[:variants]]
        return {"drafts": drafts, "attempts": attempt}

    async def review(state: PlatformState):
        if state.get("error"):
            return {}
        spec = get_spec(state["platform"])
        _emit({"stage": "reviewing", "platform": spec.id.value, "attempt": state["attempts"]})

        items = [spec.content_model.model_validate(d) for d in state["drafts"]]
        lint = [
            f"Draft {i}: {issue}" if len(items) > 1 else issue
            for i, item in enumerate(items, 1)
            for issue in spec.lint(item)
        ]
        can_retry = state["attempts"] <= max_revisions
        if lint and can_retry:
            # Hard rule violations: skip the (paid) LLM review and go straight back to the writer.
            return {"lint_issues": lint, "review": None}

        system, user = prompts.reviewer_prompts(
            spec, state["brand_profile"], state.get("sources", []), [spec.render(i) for i in items]
        )
        try:
            verdict = await llm.structured(Review, system, user, role="reviewer")
        except Exception as exc:
            log.exception("Reviewer failed for %s", spec.id)
            verdict = Review(approved=not lint, score=5, issues=[f"Automatic review unavailable: {exc}"])
        if lint:
            verdict = verdict.model_copy(update={"approved": False, "issues": [*lint, *verdict.issues]})
        return {"lint_issues": lint, "review": verdict}

    def route(state: PlatformState) -> str:
        if state.get("error"):
            return "finalize"
        r = state.get("review")
        if r is None:  # lint failed, retry allowed
            return "write"
        if r.approved or state["attempts"] > max_revisions:
            return "finalize"
        return "write"

    def finalize(state: PlatformState):
        spec = get_spec(state["platform"])
        drafts = state.get("drafts", [])
        result = PlatformResult(
            platform=spec.id,
            items=drafts,
            text=[spec.render(spec.content_model.model_validate(d)) for d in drafts],
            review=state.get("review"),
            attempts=state.get("attempts", 0),
            error=state.get("error"),
        )
        _emit({"stage": "done", "platform": spec.id.value, "approved": bool(result.review and result.review.approved)})
        return {"results": [result]}

    g = StateGraph(PlatformState, output_schema=PlatformOutput)
    g.add_node("write", write)
    g.add_node("review", review)
    g.add_node("finalize", finalize)
    g.add_edge(START, "write")
    g.add_edge("write", "review")
    g.add_conditional_edges("review", route, ["write", "finalize"])
    g.add_edge("finalize", END)
    return g.compile()


# ---------------------------------------------------------------------------
# Main graph
# ---------------------------------------------------------------------------

def build_graph(llm: LLMClient, searcher: Searcher, max_revisions: int = 2, checkpointer=None):
    async def profile(state: RunState):
        if state.get("brand_profile"):
            _emit({"stage": "profile", "status": "reused"})
            return {}
        _emit({"stage": "profile", "status": "running"})
        system, user = prompts.profile_prompts(state["brand"])
        result = await llm.structured(BrandProfile, system, user)
        _emit({"stage": "profile", "status": "done"})
        return {"brand_profile": result}

    async def planner(state: RunState):
        _emit({"stage": "planning", "status": "running"})
        system, user = prompts.planner_prompts(state["brand_profile"], state.get("topic", ""))
        plan = await llm.structured(ContentPlan, system, user)
        _emit({"stage": "planning", "status": "done", "angle": plan.angle})
        return {"plan": plan}

    async def research(state: RunState):
        queries = state["plan"].queries
        _emit({"stage": "research", "status": "running", "queries": [q.query for q in queries]})
        sources = await search_all(searcher, queries)
        _emit({"stage": "research", "status": "done", "count": len(sources)})
        return {"sources": sources}

    def fan_out(state: RunState):
        return [
            Send(
                "platform",
                {
                    "platform": p,
                    "brand_profile": state["brand_profile"],
                    "plan": state["plan"],
                    "sources": state.get("sources", []),
                    "variants": state.get("variants", 1),
                    "past_posts": state["brand"].past_posts,
                },
            )
            for p in dict.fromkeys(state["platforms"])  # de-dupe, keep order
        ]

    g = StateGraph(RunState)
    g.add_node("profile", profile)
    g.add_node("planner", planner)
    g.add_node("research", research)
    g.add_node("platform", build_platform_graph(llm, max_revisions))
    g.add_edge(START, "profile")
    g.add_edge("profile", "planner")
    g.add_edge("planner", "research")
    g.add_conditional_edges("research", fan_out, ["platform"])
    g.add_edge("platform", END)
    return g.compile(checkpointer=checkpointer)


def initial_state(req) -> RunState:
    """Build graph input from a RunRequest."""
    state: RunState = {
        "brand": req.brand,
        "platforms": list(req.platforms),
        "topic": req.topic,
        "variants": req.variants,
        "results": [],
    }
    if req.brand_profile:
        state["brand_profile"] = req.brand_profile
    return state
