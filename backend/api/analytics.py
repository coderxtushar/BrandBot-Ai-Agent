"""Analytics: how published posts perform, and recording results by hand."""

from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import current_user, publisher_dep
from backend.api.drafts import _draft_or_404
from backend.api.publications import PublicationItem, _item, _preview
from backend.db import accounts as acc
from backend.db.models import Draft, User, utcnow
from backend.db.session import get_session
from backend.schemas import (
    AnalyticsPost,
    ManualMetricsRequest,
    ManualPublicationRequest,
    Metrics,
    MetricsOut,
    MetricsSnapshot,
)

router = APIRouter(tags=["analytics"])


@router.get("/analytics/posts", response_model=list[AnalyticsPost])
async def analytics_posts(
    days: int = Query(default=90, ge=1, le=730),
    brand_id: str | None = None,
    platform: str | None = None,
    s: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Published posts with their latest numbers. The web app aggregates these in the viewer's time zone."""
    pubs = await acc.analytics_publications(s, user.id, utcnow() - timedelta(days=days), brand_id, platform)
    out = []
    for p in pubs:
        run = p.draft.platform_result.run
        out.append(
            AnalyticsPost(
                publication_id=p.id,
                draft_id=p.draft_id,
                run_id=run.id,
                brand_id=run.brand_id,
                brand_name=run.brand.name,
                platform=p.platform,
                pillar=(run.plan or {}).get("pillar"),
                angle=(run.plan or {}).get("angle"),
                preview=_preview(p),
                published_at=p.published_at,
                external_url=p.external_url,
                metrics=MetricsOut.of(p.latest_metrics),
                metrics_updated_at=p.metrics_updated_at,
                metrics_error=p.metrics_error,
            )
        )
    return out


@router.post("/analytics/refresh")
async def refresh_stats(user: User = Depends(current_user), publisher=Depends(publisher_dep)):
    """Read fresh stats for your recent posts now, instead of waiting for the next automatic round."""
    updated, failed = await publisher.collect_metrics(user_id=user.id, force=True)
    return {"updated": updated, "failed": failed}


async def _published_or_404(pub_id: str, s: AsyncSession, user: User):
    pub = await acc.get_publication(s, pub_id, user.id)
    if pub is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if pub.status != "published":
        raise HTTPException(status_code=409, detail="Results can only be added to published posts.")
    return pub


@router.get("/publications/{pub_id}/metrics", response_model=list[MetricsSnapshot])
async def metric_history(pub_id: str, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)):
    pub = await acc.get_publication(s, pub_id, user.id)
    if pub is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return await acc.metric_history(s, pub.id)


@router.post("/publications/{pub_id}/metrics", response_model=PublicationItem)
async def add_results(
    pub_id: str, req: ManualMetricsRequest, s: AsyncSession = Depends(get_session), user: User = Depends(current_user)
):
    """Type in a post's numbers (for platforms that don't share stats, or to correct them)."""
    pub = await _published_or_404(pub_id, s, user)
    await acc.record_metrics(s, pub, Metrics(**req.model_dump()), source="manual")
    return _item(await acc.get_publication(s, pub.id))


@router.post("/drafts/{draft_id}/manual-publication", response_model=PublicationItem, status_code=201)
async def posted_myself(
    req: ManualPublicationRequest,
    draft: Draft = Depends(_draft_or_404),
    s: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Record that you posted this draft yourself (e.g. on Medium), so its results can be tracked."""
    if req.url and not req.url.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="The link should start with https://")
    now = utcnow()
    when = req.published_at or now
    when = when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)
    if when > now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="That date is in the future. Use Schedule for future posts.")
    pub = await acc.create_publication(
        s,
        user_id=user.id,
        draft_id=draft.id,
        account_id=None,
        platform=draft.platform_result.platform,
        status="published",
        scheduled_at=when,
        published_at=when,
        include_image=False,
        external_url=req.url,
    )
    return _item(pub)
