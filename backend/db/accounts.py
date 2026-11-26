"""Data access for users, sessions, connected accounts and publications."""

from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.db.models import (
    Brand,
    Draft,
    OAuthState,
    PlatformAccount,
    PlatformRun,
    PostMetric,
    Publication,
    Run,
    Session,
    User,
    utcnow,
)
from backend.schemas import ConnectionOut, Metrics, MetricsOut, MetricsSnapshot, PublicationOut, UserOut
from backend.security import hash_token, new_session_token

# ---------------------------------------------------------------------------
# Users & sessions
# ---------------------------------------------------------------------------


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, name=u.name, email=u.email, created_at=u.created_at)


async def get_user_by_email(s: AsyncSession, email: str) -> User | None:
    return (await s.scalars(select(User).where(User.email == email.strip().lower()))).first()


async def create_user(s: AsyncSession, *, name: str, email: str, password_hash: str) -> User:
    first = (await s.scalar(select(func.count()).select_from(User))) == 0
    user = User(name=name.strip(), email=email.strip().lower(), password_hash=password_hash)
    s.add(user)
    await s.flush()
    if first:  # the first account adopts brands created before accounts existed
        await s.execute(update(Brand).where(Brand.user_id.is_(None)).values(user_id=user.id))
    await s.commit()
    return user


async def create_session(s: AsyncSession, user: User, days: int) -> tuple[str, datetime]:
    token = new_session_token()
    expires = utcnow() + timedelta(days=days)
    s.add(Session(token_hash=hash_token(token), user_id=user.id, expires_at=expires))
    await s.commit()
    return token, expires


async def user_for_session(s: AsyncSession, token: str) -> User | None:
    session = await s.get(Session, hash_token(token))
    if session is None or session.expires_at <= utcnow():
        return None
    return await s.get(User, session.user_id)


async def change_password(s: AsyncSession, user: User, password_hash: str, keep_token: str | None) -> int:
    """Store the new hash and sign out every other session (a stolen cookie stops working). Returns how many."""
    user.password_hash = password_hash
    others = delete(Session).where(Session.user_id == user.id)
    if keep_token:
        others = others.where(Session.token_hash != hash_token(keep_token))
    result = await s.execute(others)
    await s.commit()
    return result.rowcount or 0


async def delete_session(s: AsyncSession, token: str) -> None:
    await s.execute(delete(Session).where(Session.token_hash == hash_token(token)))
    await s.commit()


# ---------------------------------------------------------------------------
# OAuth round-trips
# ---------------------------------------------------------------------------

STATE_TTL = timedelta(minutes=15)


async def save_oauth_state(s: AsyncSession, *, state: str, user_id: str, platform: str, verifier: str) -> None:
    await s.execute(delete(OAuthState).where(OAuthState.created_at < utcnow() - STATE_TTL))  # tidy expired ones
    s.add(OAuthState(state=state, user_id=user_id, platform=platform, code_verifier=verifier))
    await s.commit()


async def pop_oauth_state(s: AsyncSession, state: str, platform: str) -> OAuthState | None:
    """One-time use: the state is deleted whether or not it's valid."""
    row = await s.get(OAuthState, state)
    if row is None:
        return None
    await s.delete(row)
    await s.commit()
    if row.platform != platform or row.created_at < utcnow() - STATE_TTL:
        return None
    return row


# ---------------------------------------------------------------------------
# Connected accounts
# ---------------------------------------------------------------------------


def connection_out(a: PlatformAccount) -> ConnectionOut:
    return ConnectionOut(
        id=a.id, platform=a.platform, display_name=a.display_name, username=a.username, expires_at=a.expires_at, created_at=a.created_at
    )


async def list_accounts(s: AsyncSession, user_id: str) -> list[PlatformAccount]:
    q = select(PlatformAccount).where(PlatformAccount.user_id == user_id).order_by(PlatformAccount.platform, PlatformAccount.created_at)
    return list((await s.scalars(q)).all())


async def get_account(s: AsyncSession, account_id: str, user_id: str) -> PlatformAccount | None:
    a = await s.get(PlatformAccount, account_id)
    return a if a is not None and a.user_id == user_id else None


async def upsert_account(s: AsyncSession, *, user_id: str, platform: str, external_id: str, **fields) -> PlatformAccount:
    """Reconnecting the same account refreshes its tokens instead of adding a duplicate."""
    q = select(PlatformAccount).where(
        PlatformAccount.user_id == user_id, PlatformAccount.platform == platform, PlatformAccount.external_id == external_id
    )
    account = (await s.scalars(q)).first()
    if account is None:
        account = PlatformAccount(user_id=user_id, platform=platform, external_id=external_id, **fields)
        s.add(account)
    else:
        for k, v in fields.items():
            setattr(account, k, v)
    await s.commit()
    return account


async def delete_account(s: AsyncSession, account: PlatformAccount) -> None:
    # Scheduled posts for this account can't go out any more.
    await s.execute(
        update(Publication)
        .where(Publication.account_id == account.id, Publication.status == "scheduled")
        .values(status="cancelled", error="The account was disconnected.")
    )
    await s.delete(account)
    await s.commit()


# ---------------------------------------------------------------------------
# Publications
# ---------------------------------------------------------------------------


def publication_out(p: Publication) -> PublicationOut:
    return PublicationOut(
        id=p.id,
        draft_id=p.draft_id,
        account_id=p.account_id,
        account_name=p.account.display_name if p.account else None,
        platform=p.platform,
        status=p.status,
        scheduled_at=p.scheduled_at,
        published_at=p.published_at,
        external_url=p.external_url,
        error=p.error,
        attempts=p.attempts,
        include_image=p.include_image,
        metrics=MetricsOut.of(p.latest_metrics),
        metrics_updated_at=p.metrics_updated_at,
        metrics_error=p.metrics_error,
    )


def _with_context(q):
    return q.options(
        selectinload(Publication.account),
        selectinload(Publication.draft).selectinload(Draft.platform_result).selectinload(PlatformRun.run).selectinload(Run.brand),
    )


async def get_publication(s: AsyncSession, pub_id: str, user_id: str | None = None) -> Publication | None:
    q = _with_context(select(Publication).where(Publication.id == pub_id)).execution_options(populate_existing=True)
    p = (await s.scalars(q)).first()
    if p is None or (user_id is not None and p.user_id != user_id):
        return None
    return p


async def list_publications(
    s: AsyncSession,
    user_id: str,
    statuses: list[str] | None,
    limit: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Publication]:
    q = _with_context(select(Publication).where(Publication.user_id == user_id))
    if statuses:
        q = q.where(Publication.status.in_(statuses))
    if start:
        q = q.where(Publication.scheduled_at >= start)
    if end:
        q = q.where(Publication.scheduled_at < end)
    q = q.order_by(Publication.scheduled_at.desc()).limit(limit)
    return list((await s.scalars(q)).all())


async def create_publication(s: AsyncSession, **fields) -> Publication:
    p = Publication(**fields)
    s.add(p)
    await s.commit()
    return await get_publication(s, p.id)


async def claim(s: AsyncSession, pub_id: str) -> bool:
    """Atomically move scheduled -> publishing. Only one worker can win, so a post never goes out twice."""
    result = await s.execute(
        update(Publication)
        .where(Publication.id == pub_id, Publication.status == "scheduled")
        .values(status="publishing", attempts=Publication.attempts + 1, updated_at=utcnow())
    )
    await s.commit()
    return result.rowcount == 1


async def due_ids(s: AsyncSession, now: datetime, limit: int = 20) -> list[str]:
    q = (
        select(Publication.id)
        .where(Publication.status == "scheduled", Publication.scheduled_at <= now)
        .order_by(Publication.scheduled_at)
        .limit(limit)
    )
    return list((await s.scalars(q)).all())


async def fail_stuck(s: AsyncSession, older_than: datetime) -> int:
    """Posts left 'publishing' by a crashed worker. We can't know if they went out, so flag them for a human."""
    result = await s.execute(
        update(Publication)
        .where(Publication.status == "publishing", Publication.updated_at < older_than)
        .values(status="failed", error="Publishing was interrupted. Check the platform before retrying.")
    )
    await s.commit()
    return result.rowcount


async def publication_keys(s: AsyncSession, *, run_id: str | None = None, brand_id: str | None = None) -> list[str]:
    """Converted image files (e.g. Instagram JPEGs) to delete along with a run or brand."""
    q = select(Publication.asset_key).join(Draft).join(PlatformRun).join(Run).where(Publication.asset_key.is_not(None))
    q = q.where(Run.id == run_id) if run_id else q.where(Run.brand_id == brand_id)
    return list((await s.scalars(q)).all())


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


async def record_metrics(s: AsyncSession, pub: Publication, metrics: Metrics, source: str = "api") -> None:
    s.add(PostMetric(publication_id=pub.id, source=source, **metrics.model_dump()))
    pub.latest_metrics = metrics.model_dump()
    pub.metrics_updated_at = utcnow()
    pub.metrics_error = None
    await s.commit()


async def metric_history(s: AsyncSession, pub_id: str) -> list[MetricsSnapshot]:
    q = select(PostMetric).where(PostMetric.publication_id == pub_id).order_by(PostMetric.captured_at)
    rows = (await s.scalars(q)).all()
    return [
        MetricsSnapshot(**MetricsOut.of(Metrics.model_validate(r, from_attributes=True)).model_dump(), captured_at=r.captured_at, source=r.source)
        for r in rows
    ]


async def due_for_metrics(
    s: AsyncSession, *, now: datetime, every: timedelta, max_age: timedelta, user_id: str | None = None, force: bool = False
) -> list[str]:
    """Published posts whose stats are worth (re)reading: recent, posted through a connected account."""
    q = select(Publication.id).where(
        Publication.status == "published",
        Publication.external_id.is_not(None),
        Publication.account_id.is_not(None),
        Publication.published_at >= now - max_age,
    )
    if user_id:
        q = q.where(Publication.user_id == user_id)
    if not force:
        q = q.where((Publication.metrics_updated_at.is_(None)) | (Publication.metrics_updated_at <= now - every))
    return list((await s.scalars(q.order_by(Publication.published_at.desc()).limit(200))).all())


async def analytics_publications(
    s: AsyncSession, user_id: str, since: datetime, brand_id: str | None = None, platform: str | None = None
) -> list[Publication]:
    q = _with_context(
        select(Publication).where(
            Publication.user_id == user_id, Publication.status == "published", Publication.published_at >= since
        )
    )
    if platform:
        q = q.where(Publication.platform == platform)
    if brand_id:
        q = q.join(Draft).join(PlatformRun).join(Run).where(Run.brand_id == brand_id)
    return list((await s.scalars(q.order_by(Publication.published_at.desc()))).all())
