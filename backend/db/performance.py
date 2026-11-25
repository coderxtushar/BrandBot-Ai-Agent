"""What has worked for a brand, distilled for the planner and writers of the next run."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.accounts import _with_context
from backend.db.models import Draft, PlatformRun, Publication, Run
from backend.platforms import get_spec
from backend.schemas import MetricsOut

EXAMPLES_PER_PLATFORM = 2


def _rank(m: MetricsOut) -> tuple:
    # Engagement rate is fairer than raw counts when views are known; otherwise fall back to interactions.
    return (m.engagement_rate if m.engagement_rate is not None else -1, m.interactions)


async def brand_performance(s: AsyncSession, brand_id: str, platforms: list[str]) -> dict | None:
    """{"examples": {platform: [text, ...]}, "pillar_notes": str}, or None when there's nothing to learn from yet."""
    q = _with_context(
        select(Publication)
        .join(Draft)
        .join(PlatformRun)
        .join(Run)
        .where(Run.brand_id == brand_id, Publication.status == "published", Publication.latest_metrics.is_not(None))
    )
    pubs = (await s.scalars(q)).all()

    scored = [(p, MetricsOut.of(p.latest_metrics)) for p in pubs]
    scored = [(p, m) for p, m in scored if m.interactions > 0]
    if not scored:
        return None

    examples: dict[str, list[str]] = {}
    for platform in platforms:
        mine = sorted((x for x in scored if x[0].platform == platform), key=lambda x: _rank(x[1]), reverse=True)
        texts = []
        for p, m in mine[:EXAMPLES_PER_PLATFORM]:
            spec = get_spec(platform)
            body = "\n\n".join(spec.post_parts(spec.content_model.model_validate(p.draft.content)))[:1200]
            stats = f"{m.interactions} interactions" + (f", {m.engagement_rate:.1%} engagement" if m.engagement_rate is not None else "")
            texts.append(f"({stats})\n{body}")
        if texts:
            examples[platform] = texts

    by_pillar: dict[str, list[int]] = defaultdict(list)
    for p, m in scored:
        pillar = (p.draft.platform_result.run.plan or {}).get("pillar")
        if pillar:
            by_pillar[pillar].append(m.interactions)
    pillar_notes = ""
    if len(by_pillar) >= 2:
        ranked = sorted(by_pillar.items(), key=lambda kv: sum(kv[1]) / len(kv[1]), reverse=True)
        parts = [f'"{k}": {round(sum(v) / len(v))} avg interactions ({len(v)} post{"s" if len(v) != 1 else ""})' for k, v in ranked]
        pillar_notes = "How this brand's topics have performed so far: " + "; ".join(parts) + "."

    if not examples and not pillar_notes:
        return None
    return {"examples": examples, "pillar_notes": pillar_notes}
