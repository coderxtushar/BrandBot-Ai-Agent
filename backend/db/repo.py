"""Data access functions. Routers call these; nothing else touches the ORM directly."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import Brand, Draft, DraftImage, DraftVersion, PlatformRun, Run, utcnow
from backend.db.accounts import publication_out
from backend.platforms import get_spec
from backend.schemas import (
    BrandCreate,
    BrandOut,
    BrandProfile,
    BrandRunRequest,
    BrandUpdate,
    DraftImageOut,
    DraftOut,
    DraftRef,
    DraftVersionOut,
    Review,
    RunDetail,
    RunResult,
    RunSummary,
    StoredPlatformResult,
)

# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------


def brand_out(b: Brand) -> BrandOut:
    return BrandOut.model_validate(b, from_attributes=True)


async def create_brand(s: AsyncSession, data: BrandCreate, user_id: str) -> Brand:
    brand = Brand(name=data.name, input=data.input.model_dump(), user_id=user_id)
    s.add(brand)
    await s.commit()
    return brand


async def list_brands(s: AsyncSession, user_id: str) -> list[Brand]:
    q = select(Brand).where(Brand.user_id == user_id).order_by(Brand.updated_at.desc())
    return list((await s.scalars(q)).all())


async def get_brand(s: AsyncSession, brand_id: str) -> Brand | None:
    return await s.get(Brand, brand_id)


async def update_brand(s: AsyncSession, brand: Brand, data: BrandUpdate) -> Brand:
    if data.name is not None:
        brand.name = data.name
    if data.input is not None:
        new_input = data.input.model_dump()
        if new_input != brand.input:
            brand.input = new_input
            brand.profile = None  # profile was derived from the old input
            brand.profile_updated_at = None
    await s.commit()
    return brand


async def set_profile(s: AsyncSession, brand: Brand, profile: BrandProfile) -> Brand:
    brand.profile = profile.model_dump()
    brand.profile_updated_at = utcnow()
    await s.commit()
    return brand


async def delete_brand(s: AsyncSession, brand: Brand) -> None:
    await s.delete(brand)
    await s.commit()


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


async def create_run(s: AsyncSession, brand: Brand, req: BrandRunRequest) -> Run:
    run = Run(
        brand_id=brand.id,
        status="running",
        platforms=[p.value for p in req.platforms],
        topic=req.topic,
        variants=req.variants,
        sources=[],
        results=[],  # initialise the collection so appending later never lazy-loads
    )
    s.add(run)
    await s.commit()
    return run


async def _store_strategy(s: AsyncSession, run: Run, profile: BrandProfile, plan, sources) -> None:
    """Save profile/plan/sources on the run, and a freshly generated profile on the brand."""
    brand = await s.get(Brand, run.brand_id)
    profile_dict = profile.model_dump()
    run.profile = profile_dict
    run.plan = plan.model_dump()
    run.sources = [src.model_dump() for src in sources]
    if brand is not None and brand.profile != profile_dict:
        brand.profile = profile_dict
        brand.profile_updated_at = utcnow()


async def mark_awaiting(s: AsyncSession, run_id: str, state: dict) -> Run:
    """The run paused for plan review: keep what it has produced so far."""
    run = await s.get(Run, run_id)
    await _store_strategy(s, run, state["brand_profile"], state["plan"], state.get("sources", []))
    run.status = "awaiting_plan"
    await s.commit()
    return await get_run(s, run_id)


async def mark_running(s: AsyncSession, run: Run) -> None:
    run.status = "running"
    run.error = None
    await s.commit()


async def complete_run(s: AsyncSession, run_id: str, result: RunResult) -> Run:
    """Store the graph output, and save a freshly generated profile on the brand."""
    run = await s.get(Run, run_id)
    await _store_strategy(s, run, result.brand_profile, result.plan, result.sources)
    run.status = "completed"
    run.finished_at = utcnow()
    for pos, r in enumerate(result.results):
        run.results.append(
            PlatformRun(
                platform=r.platform.value,
                position=pos,
                review=r.review.model_dump() if r.review else None,
                attempts=r.attempts,
                error=r.error,
                drafts=[
                    Draft(
                        position=i,
                        content=item,
                        text=text,
                        versions=[DraftVersion(source="generated", content=item, text=text)],
                    )
                    for i, (item, text) in enumerate(zip(r.items, r.text, strict=True))
                ],
            )
        )
    await s.commit()
    return await get_run(s, run_id)


async def fail_run(s: AsyncSession, run_id: str, error: str, status: str = "failed") -> None:
    run = await s.get(Run, run_id)
    if run is None or run.status not in ("running", "awaiting_plan"):
        return
    run.status = status
    run.error = error
    run.finished_at = utcnow()
    await s.commit()


async def list_runs(s: AsyncSession, brand_id: str, limit: int = 20, offset: int = 0) -> list[Run]:
    q = (
        select(Run)
        .where(Run.brand_id == brand_id)
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await s.scalars(q)).all())


async def get_run(s: AsyncSession, run_id: str) -> Run | None:
    # populate_existing refreshes relationships that were just appended in this session
    q = select(Run).where(Run.id == run_id).execution_options(populate_existing=True)
    return (await s.scalars(q)).first()


async def delete_run(s: AsyncSession, run: Run) -> None:
    await s.delete(run)
    await s.commit()


def _summary_fields(run: Run) -> dict:
    return {
        "id": run.id,
        "brand_id": run.brand_id,
        "status": run.status,
        "platforms": run.platforms,
        "topic": run.topic,
        "angle": (run.plan or {}).get("angle"),
        "approved": sum(1 for r in run.results if r.review and r.review.get("approved")),
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


def run_summary(run: Run) -> RunSummary:
    return RunSummary(**_summary_fields(run))


def _lint(platform: str, content: dict) -> list[str]:
    spec = get_spec(platform)
    return spec.lint(spec.content_model.model_validate(content))


def run_detail(run: Run) -> RunDetail:
    return RunDetail(
        **_summary_fields(run),
        variants=run.variants,
        error=run.error,
        brand_profile=run.profile,
        plan=run.plan,
        sources=run.sources or [],
        results=[
            StoredPlatformResult(
                platform=r.platform,
                items=[d.content for d in r.drafts],
                text=[d.text for d in r.drafts],
                review=r.review,
                attempts=r.attempts,
                error=r.error,
                drafts=[
                    DraftRef(
                        id=d.id,
                        status=d.status,
                        review=d.review,
                        lint=_lint(r.platform, d.content),
                        images=[image_out(i) for i in d.images],
                        publications=[publication_out(p) for p in d.publications],
                    )
                    for d in r.drafts
                ],
            )
            for r in run.results
        ],
    )


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------


async def get_draft(s: AsyncSession, draft_id: str) -> Draft | None:
    q = (
        select(Draft)
        .where(Draft.id == draft_id)
        .options(selectinload(Draft.platform_result).selectinload(PlatformRun.run).selectinload(Run.brand))
    )
    return (await s.scalars(q)).first()


def draft_out(d: Draft) -> DraftOut:
    spec = get_spec(d.platform_result.platform)
    return DraftOut(
        id=d.id,
        run_id=d.platform_result.run_id,
        platform=spec.id,
        position=d.position,
        content=d.content,
        text=d.text,
        status=d.status,
        review=d.review,
        lint=_lint(spec.id, d.content),
        updated_at=d.updated_at,
    )


async def set_draft_content(
    s: AsyncSession, d: Draft, content: dict, *, source: str, note: str | None = None, review: Review | None = None
) -> Draft:
    """Replace a draft's content (already validated) and record a version."""
    spec = get_spec(d.platform_result.platform)
    text = spec.render(spec.content_model.model_validate(content))
    review_dict = review.model_dump() if review else None
    d.content, d.text, d.review, d.status = content, text, review_dict, "draft"
    s.add(DraftVersion(draft_id=d.id, source=source, note=note, content=content, text=text, review=review_dict))
    await s.commit()
    return d


async def set_draft_status(s: AsyncSession, d: Draft, status: str) -> Draft:
    d.status = status
    await s.commit()
    return d


async def list_versions(s: AsyncSession, draft_id: str) -> list[DraftVersion]:
    q = select(DraftVersion).where(DraftVersion.draft_id == draft_id).order_by(DraftVersion.created_at.desc())
    return list((await s.scalars(q)).all())


async def get_version(s: AsyncSession, draft_id: str, version_id: str) -> DraftVersion | None:
    v = await s.get(DraftVersion, version_id)
    return v if v is not None and v.draft_id == draft_id else None


async def count_versions(s: AsyncSession, draft_id: str) -> int:
    return await s.scalar(select(func.count()).where(DraftVersion.draft_id == draft_id)) or 0


def version_out(v: DraftVersion) -> DraftVersionOut:
    return DraftVersionOut.model_validate(v, from_attributes=True)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------


def image_out(img: DraftImage) -> DraftImageOut:
    return DraftImageOut(
        id=img.id,
        draft_id=img.draft_id,
        url=f"/media/{img.storage_key}",
        prompt=img.prompt,
        alt_text=img.alt_text,
        aspect_ratio=img.aspect_ratio,
        style=img.style,
        model=img.model,
        created_at=img.created_at,
    )


async def add_image(s: AsyncSession, draft: Draft, **fields) -> DraftImage:
    img = DraftImage(draft_id=draft.id, **fields)
    s.add(img)
    await s.commit()
    return img


async def get_image(s: AsyncSession, image_id: str, user_id: str) -> DraftImage | None:
    q = (
        select(DraftImage)
        .join(Draft)
        .join(PlatformRun)
        .join(Run)
        .join(Brand)
        .where(DraftImage.id == image_id, Brand.user_id == user_id)
    )
    return (await s.scalars(q)).first()


async def list_images(s: AsyncSession, draft_id: str) -> list[DraftImage]:
    q = select(DraftImage).where(DraftImage.draft_id == draft_id).order_by(DraftImage.created_at.desc())
    return list((await s.scalars(q)).all())


async def delete_image(s: AsyncSession, img: DraftImage) -> str:
    key = img.storage_key
    await s.delete(img)
    await s.commit()
    return key


async def media_keys(s: AsyncSession, *, run_id: str | None = None, brand_id: str | None = None) -> list[str]:
    """Storage keys of every image under a run or brand (to delete the files with the rows)."""
    q = select(DraftImage.storage_key).join(Draft).join(PlatformRun).join(Run)
    q = q.where(Run.id == run_id) if run_id else q.where(Run.brand_id == brand_id)
    return list((await s.scalars(q)).all())
