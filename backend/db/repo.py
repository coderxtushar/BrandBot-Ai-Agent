"""Data access functions. Routers call these; nothing else touches the ORM directly."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Brand, Draft, PlatformRun, Run, utcnow
from backend.schemas import (
    BrandCreate,
    BrandOut,
    BrandProfile,
    BrandRunRequest,
    BrandUpdate,
    DraftRef,
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


async def create_brand(s: AsyncSession, data: BrandCreate) -> Brand:
    brand = Brand(name=data.name, input=data.input.model_dump())
    s.add(brand)
    await s.commit()
    return brand


async def list_brands(s: AsyncSession) -> list[Brand]:
    return list((await s.scalars(select(Brand).order_by(Brand.updated_at.desc()))).all())


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


async def complete_run(s: AsyncSession, run_id: str, result: RunResult) -> Run:
    """Store the graph output, and save a freshly generated profile on the brand."""
    run = await s.get(Run, run_id)
    brand = await s.get(Brand, run.brand_id)
    profile = result.brand_profile.model_dump()

    run.profile = profile
    run.plan = result.plan.model_dump()
    run.sources = [src.model_dump() for src in result.sources]
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
                    Draft(position=i, content=item, text=text)
                    for i, (item, text) in enumerate(zip(r.items, r.text, strict=True))
                ],
            )
        )
    if brand is not None and brand.profile != profile:
        brand.profile = profile
        brand.profile_updated_at = utcnow()
    await s.commit()
    return await get_run(s, run_id)


async def fail_run(s: AsyncSession, run_id: str, error: str, status: str = "failed") -> None:
    run = await s.get(Run, run_id)
    if run is None or run.status != "running":
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
                drafts=[DraftRef(id=d.id, status=d.status) for d in r.drafts],
            )
            for r in run.results
        ],
    )
