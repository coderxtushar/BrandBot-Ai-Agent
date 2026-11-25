"""Visuals: AI-generated images for drafts, and serving stored media."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents import prompts
from backend.api.deps import Services, services_dep, storage_dep
from backend.api.drafts import _draft_or_404
from backend.db import repo
from backend.db.models import Draft
from backend.db.session import get_session
from backend.platforms import get_spec
from backend.schemas import BrandProfile, DraftImageOut, ImagePrompt, ImageRequest

router = APIRouter(tags=["images"])
log = logging.getLogger("brandbot")


@router.post("/drafts/{draft_id}/images", response_model=DraftImageOut, status_code=201)
async def generate_image(
    req: ImageRequest,
    draft: Draft = Depends(_draft_or_404),
    s: AsyncSession = Depends(get_session),
    services: Services = Depends(services_dep),
    storage=Depends(storage_dep),
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
    try:
        brief = await services.llm.structured(ImagePrompt, system, user, role="writer")
        image = await services.images.generate(brief.prompt, spec.image_aspect)
    except Exception as exc:
        log.exception("Image generation failed for draft %s", draft.id)
        raise HTTPException(status_code=502, detail=f"Image generation failed: {exc}") from exc

    key = storage.save(image.data, image.mime)
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
async def delete_image(image_id: str, s: AsyncSession = Depends(get_session), storage=Depends(storage_dep)):
    img = await repo.get_image(s, image_id)
    if img is None:
        raise HTTPException(status_code=404, detail="Image not found")
    storage.delete(await repo.delete_image(s, img))
    return Response(status_code=204)


@router.get("/media/{key:path}", include_in_schema=False)
async def media(key: str, storage=Depends(storage_dep)):
    path = storage.path(key)
    if path is None:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        path,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",  # keys are random and never reused
            "X-Content-Type-Options": "nosniff",
            # SVGs are served as images only: no scripts, no external loads
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )
