"""Rate limits stored in the database, so every API instance (Cloud Run scales out) shares one count.

Fixed windows: "10/hour" allows 10 requests in each clock hour per subject. Simple and cheap (one upsert per
rule); the trade-off is that a burst straddling the window edge can reach twice the limit, which is fine for
cost control. Rejected requests count too, so hammering doesn't shorten the wait.
"""

import math
import random
import re
import time
from dataclasses import dataclass
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db.models import RateLimitCounter, User
from backend.db.session import get_session
from backend.observability import client_ip

_UNITS = {"s": 1, "sec": 1, "second": 1, "m": 60, "min": 60, "minute": 60, "h": 3600, "hour": 3600, "d": 86400, "day": 86400}
_RULE = re.compile(r"^\s*(\d+)\s*/\s*(\d*)\s*([a-z]+?)s?\s*$")


@dataclass(frozen=True)
class Rule:
    count: int
    seconds: int

    @property
    def period(self) -> str:
        for name, size in (("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)):
            if self.seconds % size == 0:
                n = self.seconds // size
                return name if n == 1 else f"{n} {name}s"
        return f"{self.seconds} seconds"  # unreachable: every size divides by 1


@lru_cache
def parse_rules(spec: str) -> tuple[Rule, ...]:
    """'10/hour, 40/day, 5/10minutes' -> rules. Raises ValueError on a typo so bad config fails loudly."""
    rules = []
    for part in filter(None, (p.strip() for p in spec.split(","))):
        m = _RULE.match(part.lower())
        if not m or m.group(3) not in _UNITS:
            raise ValueError(f"Bad rate limit {part!r}; use 'count/period' like '10/hour' or '10/5minutes'.")
        count, mult, unit = int(m.group(1)), int(m.group(2) or 1), m.group(3)
        rules.append(Rule(count, mult * _UNITS[unit]))
    return tuple(rules)


def _wait(seconds: float) -> str:
    if seconds < 90:
        return f"{max(1, math.ceil(seconds))} seconds"
    if seconds < 5400:
        return f"{math.ceil(seconds / 60)} minutes"
    return f"{math.ceil(seconds / 3600)} hours"


class RateLimited(HTTPException):
    def __init__(self, what: str, rule: Rule, retry_after: float):
        super().__init__(
            status_code=429,
            detail=f"You've reached the limit of {rule.count} {what} per {rule.period}. Try again in {_wait(retry_after)}.",
            headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
        )


async def hit(s: AsyncSession, name: str, subject: str, rules: tuple[Rule, ...], *, what: str, now: float | None = None) -> None:
    """Count one request against every rule; raise RateLimited if any is over its limit."""
    now = time.time() if now is None else now
    insert = pg_insert if s.get_bind().dialect.name == "postgresql" else sqlite_insert
    exceeded: tuple[Rule, float] | None = None
    for rule in rules:
        window = int(now // rule.seconds)
        ends = (window + 1) * rule.seconds
        stmt = (
            insert(RateLimitCounter)
            .values(key=f"{name}:{subject}:{rule.seconds}:{window}"[:255], count=1, expires_at=ends)
            .on_conflict_do_update(index_elements=["key"], set_={"count": RateLimitCounter.count + 1})
            .returning(RateLimitCounter.count)
        )
        count = (await s.execute(stmt)).scalar_one()
        if count > rule.count and (exceeded is None or ends - now > exceeded[1]):
            exceeded = (rule, ends - now)  # report the longest wait
    if random.random() < 0.01:  # keep the table small without a separate job
        await purge_expired(s, now)
    await s.commit()
    if exceeded:
        raise RateLimited(what, *exceeded)


async def purge_expired(s: AsyncSession, now: float | None = None) -> int:
    result = await s.execute(delete(RateLimitCounter).where(RateLimitCounter.expires_at <= int(now or time.time())))
    return result.rowcount or 0


async def check(s: AsyncSession, name: str, subject: str, setting: str, *, what: str) -> None:
    """Apply the limits configured in settings.<setting> (no-op when limits are off)."""
    settings = get_settings()
    if settings.rate_limits_enabled:
        await hit(s, name, subject, parse_rules(getattr(settings, setting)), what=what)


def per_user(name: str, setting: str, what: str):
    """Dependency: limit a signed-in user's use of an expensive endpoint (AI calls cost money)."""
    from backend.api.deps import current_user  # deps imports the graph; keep this module light

    async def dep(user: User = Depends(current_user), s: AsyncSession = Depends(get_session)) -> None:
        await check(s, name, user.id, setting, what=what)

    return Depends(dep)


def ip_of(request: Request) -> str:
    return client_ip(request.headers, request.client.host if request.client else None, get_settings().trusted_proxy_hops)
