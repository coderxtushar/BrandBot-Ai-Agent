"""Visuals: AI-generated images for drafts, and serving stored media."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from langsmith import trace
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents import prompts
from backend.api.deps import Services, current_user, services_dep, storage_dep
from backend.api.drafts import _draft_or_404
from backend.db import repo
from backend.db.models import Draft, User
from backend.db.session import get_session
from backend.observability import trace_config
from backend.platforms import get_spec
from backend.ratelimit import per_user
from backend.schemas import BrandProfile, DraftImageOut, ImagePrompt, ImageRequest
from backend.services.storage import mime_for

router = APIRouter(tags=["images"])
log = logging.getLogger("brandbot")


@router.post(
    "/drafts/{draft_id}/images",
    response_model=DraftImageOut,
    status_code=201,
    dependencies=[per_user("images", "rate_limit_images", "generated images")],
)
async def generate_image(
    req: ImageRequest,
    draft: Draft = Depends(_draft_or_404),
    s: AsyncSession = Depends(get_session),
    services: Services = Depends(services_dep),
    storage=Depends(storage_dep),
    me: User = Depends(current_user),
):
    """Art-direct and generate an on-brand image for this draft, sized for its platform."""
    run = draft.platform_result.run
    if run.profile is None:
        raise HTTPException(status_code=409, detail="This run has no brand profile to design from.")
    spec = get_spec(draft.platform_result.platform)

    system, user = prompts.image_prompts(
        spec,
        BrandProfile.model_validate(run.profile),
        draft.text,
        style=req.style,
        idea=req.idea,
        suggested=draft.content.get("image_prompt", ""),
    )
    meta = trace_config("image", user_id=me.id, brand_id=run.brand_id, run_id=run.id, draft_id=draft.id, platforms=[spec.id])
    try:
        async with trace(meta["run_name"], tags=meta["tags"], metadata=meta["metadata"]):  # no-op unless tracing is on
            brief = await services.llm.structured(ImagePrompt, system, user, role="writer")
            image = await services.images.generate(brief.prompt, spec.image_aspect)
    except Exception as exc:
        log.exception("Image generation failed for draft %s", draft.id)
        raise HTTPException(status_code=502, detail=_failure_message(exc)) from exc

    key = await storage.save(image.data, image.mime)
    img = await repo.add_image(
        s,
        draft,
        storage_key=key,
        mime=image.mime,
        prompt=brief.prompt,
        alt_text=brief.alt_text,
        aspect_ratio=spec.image_aspect,
        style=req.style,
        model=image.model,
    )
    return repo.image_out(img)


@router.get("/drafts/{draft_id}/images", response_model=list[DraftImageOut])
async def list_images(draft: Draft = Depends(_draft_or_404), s: AsyncSession = Depends(get_session)):
    return [repo.image_out(i) for i in await repo.list_images(s, draft.id)]


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(
    image_id: str, s: AsyncSession = Depends(get_session), storage=Depends(storage_dep), user: User = Depends(current_user)
):
    img = await repo.get_image(s, image_id, user.id)
    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")
    await storage.delete(await repo.delete_image(s, img))
    return Response(status_code=204)


@router.get("/media/{key:path}", include_in_schema=False)
async def media(key: str, storage=Depends(storage_dep)):
    data = await storage.read(key)
    if data is None:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(
        data,
        media_type=mime_for(key),
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",  # keys are random and never reused
            "X-Content-Type-Options": "nosniff",
            # SVGs are served as images only: no scripts, no external loads
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


def _failure_message(exc: Exception) -> str:
    """Say what to do about the common Gemini failures instead of passing on Google's raw error."""
    text = str(exc)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        if "free_tier" in text and "limit: 0" in text:
            return (
                "Image generation isn't included in the Gemini API free tier. Turn on billing for the Google "
                "project that owns GOOGLE_API_KEY (in AI Studio) to create images."
            )
        return "The image model is over its quota right now. Try again in a minute."
    return f"Image generation failed: {text}"
