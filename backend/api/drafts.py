"""Editing loop for individual drafts: edit, approve/reject, AI rewrite, version history."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import current_user, platform_graph_dep
from backend.db import repo
from backend.db.models import Draft, User
from backend.db.session import get_session
from backend.platforms import get_spec
from backend.observability import trace_config
from backend.ratelimit import per_user
from backend.schemas import (
    BrandInput,
    BrandProfile,
    ContentPlan,
    DraftOut,
    DraftUpdate,
    DraftVersionOut,
    RewriteRequest,
    Source,
)

router = APIRouter(prefix="/drafts", tags=["drafts"])

_VERSION_NAMES = {
    "generated": "original",
    "edited": "hand-edited",
    "rewrite": "AI-rewritten",
    "regenerate": "fresh",
    "restored": "restored",
}
log = logging.getLogger("brandbot")


async def _draft_or_404(
    draft_id: str, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)
) -> Draft:
    draft = await repo.get_draft(s, draft_id)
    if draft is None or draft.platform_result.run.brand.user_id != user.id:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.get("/{draft_id}", response_model=DraftOut)
async def get_draft(draft: Draft = Depends(_draft_or_404)):
    return repo.draft_out(draft)


@router.patch("/{draft_id}", response_model=DraftOut)
async def update_draft(data: DraftUpdate, draft: Draft = Depends(_draft_or_404), s: AsyncSession = Depends(get_session)):
    """Save a hand edit (validated against the platform's format) and/or approve or reject the draft."""
    if data.content is not None:
        spec = get_spec(draft.platform_result.platform)
        try:
            content = spec.content_model.model_validate(data.content).model_dump()
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors(include_url=False, include_context=False)) from exc
        if content != draft.content:
            await repo.set_draft_content(s, draft, content, source="edited")
    if data.status is not None:
        await repo.set_draft_status(s, draft, data.status)
    return repo.draft_out(draft)


@router.post("/{draft_id}/rewrite", response_model=DraftOut, dependencies=[per_user("rewrites", "rate_limit_rewrites", "AI rewrites")])
async def rewrite_draft(
    req: RewriteRequest,
    draft: Draft = Depends(_draft_or_404),
    s: AsyncSession = Depends(get_session),
    platform_graph=Depends(platform_graph_dep),
    user: User = Depends(current_user),
):
    """Ask the AI to rewrite this draft (or write a fresh one). It goes through the same lint + review loop."""
    instruction = req.text()
    if not instruction and not req.fresh:
        raise HTTPException(status_code=422, detail="Choose a preset, write an instruction, or ask for a fresh draft.")
    run = draft.platform_result.run
    if run.plan is None or run.profile is None:
        raise HTTPException(status_code=409, detail="This run has no plan to write from.")

    state = {
        "platform": draft.platform_result.platform,
        "brand_profile": BrandProfile.model_validate(run.profile),
        "plan": ContentPlan.model_validate(run.plan),
        "sources": [Source.model_validate(x) for x in run.sources or []],
        "variants": 1,
        "past_posts": BrandInput.model_validate(run.brand.input).past_posts,
        "guidance": "",
        "seed": draft.content,
        "instruction": instruction,
        "fresh": req.fresh,
    }
    config = trace_config(
        "fresh draft" if req.fresh else "rewrite",
        user_id=user.id,
        brand_id=run.brand_id,
        run_id=run.id,
        draft_id=draft.id,
        platforms=[draft.platform_result.platform],
    )
    out = await platform_graph.ainvoke(state, config)
    result = out["results"][0]
    if result.error or not result.items:
        raise HTTPException(status_code=502, detail=result.error or "The writer returned nothing.")

    await repo.set_draft_content(
        s,
        draft,
        result.items[0],
        source="regenerate" if req.fresh else "rewrite",
        note=instruction or None,
        review=result.review,
    )
    return repo.draft_out(draft)


@router.get("/{draft_id}/versions", response_model=list[DraftVersionOut])
async def list_versions(draft: Draft = Depends(_draft_or_404), s: AsyncSession = Depends(get_session)):
    """Every state of this draft, newest first."""
    return [repo.version_out(v) for v in await repo.list_versions(s, draft.id)]


@router.post("/{draft_id}/versions/{version_id}/restore", response_model=DraftOut)
async def restore_version(version_id: str, draft: Draft = Depends(_draft_or_404), s: AsyncSession = Depends(get_session)):
    version = await repo.get_version(s, draft.id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    review = version.review
    await repo.set_draft_content(
        s, draft, version.content, source="restored", note=f"Restored the {_VERSION_NAMES.get(version.source, version.source)} version"
    )
    if review:  # bring the version's review back with it
        draft.review = review
        await s.commit()
    return repo.draft_out(draft)
