"""Publishing drafts now or on a schedule."""

from datetime import UTC, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import clients_dep, current_user, publisher_dep
from backend.api.drafts import _draft_or_404
from backend.db import accounts as acc
from backend.db.models import Draft, User, utcnow
from backend.db.session import get_session
from backend.platforms import get_spec
from backend.schemas import PUBLISHABLE, PublicationOut, PublishRequest, RescheduleRequest

router = APIRouter(tags=["publishing"])

NOW_SLACK = timedelta(seconds=30)  # "in 20 seconds" just means now


class PublicationItem(PublicationOut):
    """A publication with enough context to show it in the schedule."""

    run_id: str
    brand_name: str
    preview: str


def _preview(p) -> str:
    """The text that actually gets posted (e.g. the Instagram caption, not the slide outline)."""
    spec = get_spec(p.platform)
    parts = spec.post_parts(spec.content_model.model_validate(p.draft.content)) or [p.draft.text]
    return parts[0][:200]


def _item(p) -> PublicationItem:
    run = p.draft.platform_result.run
    return PublicationItem(**acc.publication_out(p).model_dump(), run_id=run.id, brand_name=run.brand.name, preview=_preview(p))


def _when(value):
    """Naive datetimes are taken as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.post("/drafts/{draft_id}/publications", response_model=PublicationItem, status_code=201)
async def publish_draft(
    req: PublishRequest,
    draft: Draft = Depends(_draft_or_404),
    s: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
    clients=Depends(clients_dep),
    publisher=Depends(publisher_dep),
):
    """Publish now (scheduled_at empty) or schedule for later."""
    platform = draft.platform_result.platform
    spec = get_spec(platform)
    if platform not in PUBLISHABLE:
        raise HTTPException(status_code=422, detail=f"{spec.label} has no publishing API. Copy or download the draft instead.")
    account = await acc.get_account(s, req.account_id, user.id)
    if account is None or account.platform != platform:
        raise HTTPException(status_code=422, detail=f"Choose a connected {spec.label} account.")
    problems = spec.lint(spec.content_model.model_validate(draft.content))
    if problems:
        raise HTTPException(status_code=422, detail=f"Fix this first: {problems[0]}")
    client = clients[platform]
    if client.image_required and not (req.include_image and draft.images):
        raise HTTPException(status_code=422, detail=f"{spec.label} posts need an image. Generate one for this draft first.")

    now = utcnow()
    when = _when(req.scheduled_at) if req.scheduled_at else now
    if when < now - timedelta(minutes=1):
        raise HTTPException(status_code=422, detail="That time is in the past. Pick a future time or publish now.")
    immediate = when <= now + NOW_SLACK

    pub = await acc.create_publication(
        s,
        user_id=user.id,
        draft_id=draft.id,
        account_id=account.id,
        platform=platform,
        status="scheduled",
        scheduled_at=now if immediate else when,
        include_image=req.include_image,
        image_id=draft.images[0].id if (req.include_image and draft.images) else None,
    )
    if immediate:
        await publisher.publish_now(pub.id)
        pub = await acc.get_publication(s, pub.id)
    return _item(pub)


@router.get("/publications", response_model=list[PublicationItem])
async def list_publications(
    status: list[Literal["scheduled", "publishing", "published", "failed", "cancelled"]] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    s: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    return [_item(p) for p in await acc.list_publications(s, user.id, status, limit)]


async def _pub_or_404(pub_id: str, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)):
    pub = await acc.get_publication(s, pub_id, user.id)
    if pub is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return pub


@router.patch("/publications/{pub_id}", response_model=PublicationItem)
async def reschedule(req: RescheduleRequest, pub=Depends(_pub_or_404), s: AsyncSession = Depends(get_session)):
    if pub.status not in ("scheduled", "failed", "cancelled"):
        raise HTTPException(status_code=409, detail=f"A {pub.status} post can't be rescheduled.")
    when = _when(req.scheduled_at)
    if when < utcnow() - timedelta(minutes=1):
        raise HTTPException(status_code=422, detail="That time is in the past.")
    if pub.account_id is None:
        raise HTTPException(status_code=409, detail="The account was disconnected. Publish the draft again with a connected account.")
    pub.scheduled_at, pub.status, pub.error = when, "scheduled", None
    await s.commit()
    return _item(await acc.get_publication(s, pub.id))


@router.post("/publications/{pub_id}/cancel", response_model=PublicationItem)
async def cancel(pub=Depends(_pub_or_404), s: AsyncSession = Depends(get_session)):
    if pub.status != "scheduled":
        raise HTTPException(status_code=409, detail=f"Only scheduled posts can be cancelled (this one is {pub.status}).")
    pub.status = "cancelled"
    await s.commit()
    return _item(await acc.get_publication(s, pub.id))


@router.post("/publications/{pub_id}/retry", response_model=PublicationItem)
async def retry(pub=Depends(_pub_or_404), s: AsyncSession = Depends(get_session), publisher=Depends(publisher_dep)):
    """Try a failed post again right now."""
    if pub.status != "failed":
        raise HTTPException(status_code=409, detail=f"Only failed posts can be retried (this one is {pub.status}).")
    pub.status, pub.scheduled_at, pub.attempts = "scheduled", utcnow(), 0
    await s.commit()
    await publisher.publish_now(pub.id)
    return _item(await acc.get_publication(s, pub.id))
