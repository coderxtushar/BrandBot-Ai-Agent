"""Endpoints for infrastructure, not people. Cloud Scheduler calls /internal/tick on a schedule.

On Cloud Run an instance only gets CPU while it serves a request and may scale to zero, so the in-process
scheduler can't be trusted there: set SCHEDULER_ENABLED=false and let a cron call this instead.
"""

import hmac
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.api.deps import publisher_dep
from backend.config import get_settings
from backend.db.session import Database, get_database
from backend.ratelimit import purge_expired

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)
log = logging.getLogger("brandbot")


def require_cron(request: Request) -> None:
    secret = get_settings().cron_secret
    sent = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(sent.encode(), f"Bearer {secret}".encode()):
        raise HTTPException(status_code=404, detail="Not Found")  # don't advertise the endpoint


@router.post("/tick", dependencies=[Depends(require_cron)])
async def tick(publisher=Depends(publisher_dep), db: Database = Depends(get_database)):
    """Publish due posts, refresh stats that are due, and drop expired rate-limit counters.

    Safe to call often and from overlapping invocations: posts are claimed atomically before publishing."""
    published = await publisher.run_due()
    stats_updated, stats_failed = await publisher.collect_metrics()
    async with db.sessions() as s:
        purged = await purge_expired(s)
        await s.commit()
    result = {"published": published, "stats_updated": stats_updated, "stats_failed": stats_failed, "limits_purged": purged}
    if published or stats_updated or stats_failed:
        log.info("Tick: %s", result)
    return result
