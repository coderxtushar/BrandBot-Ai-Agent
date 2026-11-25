"""Connecting accounts and publishing drafts (with fake platform clients)."""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select, update

from backend.db.models import PlatformAccount, Publication, utcnow
from backend.platforms import get_spec
from backend.publishing.base import PublishError
from backend.schemas import XThread
from tests.conftest import stream
from tests.test_auth import db_call
from tests.test_brands import make_brand

ALL = ["linkedin", "x", "threads", "instagram", "medium"]


def connect(client, platform: str) -> dict:
    url = client.post(f"/connections/{platform}/start").json()["url"]
    callback = urlparse(url)
    res = client.get(f"{callback.path}?{callback.query}", follow_redirects=False)
    assert res.status_code == 303 and f"connected={platform}" in res.headers["location"], res.headers.get("location")
    return next(a for a in client.get("/connections").json()["accounts"] if a["platform"] == platform)


@pytest.fixture
def run(client):
    b = make_brand(client)
    return stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": ALL})[-1][1]


def draft(run, platform):
    return next(r for r in run["results"] if r["platform"] == platform)["drafts"][0]["id"]


def publish(client, draft_id, account_id, **body):
    return client.post(f"/drafts/{draft_id}/publications", json={"account_id": account_id, **body})


def run_scheduler(client) -> int:
    return client.portal.call(client.app.state.publisher.run_due)


def set_due(client, pub_id):
    async def go(s):
        await s.execute(update(Publication).where(Publication.id == pub_id).values(scheduled_at=utcnow() - timedelta(seconds=5)))
        await s.commit()

    db_call(client, go)


# --- connections ------------------------------------------------------------


def test_lists_publishable_platforms(client):
    info = client.get("/connections").json()
    assert [p["platform"] for p in info["platforms"]] == ["linkedin", "x", "threads", "instagram"]
    assert all(p["available"] for p in info["platforms"]) and info["accounts"] == []


def test_connect_flow_stores_encrypted_tokens(client):
    account = connect(client, "linkedin")
    assert account["display_name"] == "Demo LinkedIn account"
    rows = db_call(client, lambda s: s.scalars(select(PlatformAccount.access_token)))
    stored = list(rows)
    assert stored and all("demo-access" not in t for t in stored)  # encrypted at rest
    # reconnecting the same account doesn't duplicate it
    connect(client, "linkedin")
    assert len(client.get("/connections").json()["accounts"]) == 1


def test_connect_rejects_bad_or_reused_state(client):
    url = client.post("/connections/x/start").json()["url"]
    q = parse_qs(urlparse(url).query)
    bad = client.get("/connections/x/callback", params={"code": "demo-code", "state": "forged"}, follow_redirects=False)
    assert "error=" in bad.headers["location"]
    good = client.get("/connections/x/callback", params={"code": "demo-code", "state": q["state"][0]}, follow_redirects=False)
    assert "connected=x" in good.headers["location"]
    again = client.get("/connections/x/callback", params={"code": "demo-code", "state": q["state"][0]}, follow_redirects=False)
    assert "error=" in again.headers["location"]  # one-time use


def test_denied_consent_comes_back_with_error(client):
    url = client.post("/connections/threads/start").json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    res = client.get("/connections/threads/callback", params={"state": state, "error": "access_denied"}, follow_redirects=False)
    assert "error=" in res.headers["location"]


# --- publishing ---------------------------------------------------------------


def test_publish_linkedin_now_with_image(client, run, platforms):
    account = connect(client, "linkedin")
    did = draft(run, "linkedin")
    client.post(f"/drafts/{did}/images", json={})
    res = publish(client, did, account["id"])
    assert res.status_code == 201, res.text
    pub = res.json()
    assert pub["status"] == "published" and pub["external_url"].startswith("https://example.com/demo/linkedin/")
    assert pub["brand_name"] == "Data Coach" and pub["preview"]
    creds, payload = platforms["linkedin"].posts[0]
    assert creds.access_token.startswith("demo-access") and payload.image is not None
    assert payload.image.public_url.startswith("http://localhost:8000/media/images/")
    # the run shows it on the draft
    saved = client.get(f"/runs/{run['id']}").json()
    linkedin = next(r for r in saved["results"] if r["platform"] == "linkedin")
    assert linkedin["drafts"][0]["publications"][0]["status"] == "published"


def test_x_thread_parts_match_preview_and_skip_images(client, run, platforms):
    account = connect(client, "x")
    did = draft(run, "x")
    client.post(f"/drafts/{did}/images", json={})
    assert publish(client, did, account["id"]).json()["status"] == "published"
    _, payload = platforms["x"].posts[0]
    content = client.get(f"/drafts/{did}").json()["content"]
    assert payload.parts == get_spec("x").post_parts(XThread.model_validate(content))
    assert payload.parts[1].startswith("2/3 ") and payload.image is None


def test_instagram_needs_an_image(client, run):
    account = connect(client, "instagram")
    did = draft(run, "instagram")
    assert publish(client, did, account["id"]).status_code == 422
    client.post(f"/drafts/{did}/images", json={})
    assert publish(client, did, account["id"]).json()["status"] == "published"


def test_rules_checked_before_publishing(client, run):
    x = connect(client, "x")
    li = connect(client, "linkedin")
    did = draft(run, "x")
    client.patch(f"/drafts/{did}", json={"content": {"tweets": ["x" * 300], "hashtags": []}})
    res = publish(client, did, x["id"])
    assert res.status_code == 422 and "280" in res.json()["detail"]
    assert publish(client, draft(run, "linkedin"), x["id"]).status_code == 422  # wrong platform's account
    medium = publish(client, draft(run, "medium"), li["id"])
    assert medium.status_code == 422 and "no publishing API" in medium.json()["detail"]
    assert publish(client, did, "nope").status_code == 422


def test_schedule_then_scheduler_publishes_when_due(client, run, platforms):
    account = connect(client, "threads")
    later = (utcnow() + timedelta(hours=2)).isoformat()
    pub = publish(client, draft(run, "threads"), account["id"], scheduled_at=later).json()
    assert pub["status"] == "scheduled"
    assert run_scheduler(client) == 0 and platforms["threads"].posts == []

    set_due(client, pub["id"])
    assert run_scheduler(client) == 1
    [item] = client.get("/publications", params={"status": ["published"]}).json()
    assert item["id"] == pub["id"] and item["published_at"]
    assert run_scheduler(client) == 0  # never twice


def test_claim_is_atomic(client, run):
    from backend.db import accounts as acc

    account = connect(client, "linkedin")
    pub = publish(client, draft(run, "linkedin"), account["id"], scheduled_at=(utcnow() + timedelta(hours=1)).isoformat()).json()
    first = db_call(client, lambda s: acc.claim(s, pub["id"]))
    second = db_call(client, lambda s: acc.claim(s, pub["id"]))
    assert first is True and second is False


def test_temporary_failure_retries_then_permanent_failure_can_be_retried(client, run, platforms):
    account = connect(client, "linkedin")
    platforms["linkedin"].fail_next = PublishError("LinkedIn is down (503)", retryable=True)
    pub = publish(client, draft(run, "linkedin"), account["id"]).json()
    assert pub["status"] == "scheduled" and pub["attempts"] == 1 and "Retrying" in pub["error"]

    set_due(client, pub["id"])
    platforms["linkedin"].fail_next = PublishError("Duplicate post", retryable=False)
    run_scheduler(client)
    failed = client.get("/publications", params={"status": ["failed"]}).json()[0]
    assert failed["error"] == "Duplicate post"

    retried = client.post(f"/publications/{pub['id']}/retry").json()
    assert retried["status"] == "published"


def test_cancel_and_reschedule(client, run):
    account = connect(client, "linkedin")
    soon = (utcnow() + timedelta(hours=1)).isoformat()
    pub = publish(client, draft(run, "linkedin"), account["id"], scheduled_at=soon).json()

    later = (utcnow() + timedelta(days=1)).isoformat()
    moved = client.patch(f"/publications/{pub['id']}", json={"scheduled_at": later}).json()
    assert moved["scheduled_at"][:16] == later[:16]
    assert client.patch(f"/publications/{pub['id']}", json={"scheduled_at": "2020-01-01T00:00:00Z"}).status_code == 422

    assert client.post(f"/publications/{pub['id']}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/publications/{pub['id']}/cancel").status_code == 409


def test_past_times_are_rejected(client, run):
    account = connect(client, "linkedin")
    res = publish(client, draft(run, "linkedin"), account["id"], scheduled_at="2020-01-01T09:00:00Z")
    assert res.status_code == 422


def test_disconnecting_cancels_scheduled_posts(client, run):
    account = connect(client, "x")
    pub = publish(client, draft(run, "x"), account["id"], scheduled_at=(utcnow() + timedelta(hours=3)).isoformat()).json()
    assert client.delete(f"/connections/{account['id']}").status_code == 204
    [item] = client.get("/publications").json()
    assert item["id"] == pub["id"] and item["status"] == "cancelled" and "disconnected" in item["error"]


def test_expiring_tokens_are_refreshed_and_stored_encrypted(client, run, platforms):
    account = connect(client, "x")

    async def expire(s):
        await s.execute(update(PlatformAccount).where(PlatformAccount.id == account["id"]).values(expires_at=utcnow() + timedelta(minutes=5)))
        await s.commit()

    db_call(client, expire)
    publish(client, draft(run, "x"), account["id"])
    creds, _ = platforms["x"].posts[0]
    assert creds.access_token == "demo-access-x-r1" and platforms["x"].refreshed == 1
    stored = list(db_call(client, lambda s: s.scalars(select(PlatformAccount.access_token))))
    assert "demo-access-x-r1" not in stored[0]


def test_stuck_publishing_is_flagged(client, run):
    account = connect(client, "linkedin")
    pub = publish(client, draft(run, "linkedin"), account["id"], scheduled_at=(utcnow() + timedelta(hours=1)).isoformat()).json()

    async def stick(s):
        await s.execute(
            update(Publication).where(Publication.id == pub["id"]).values(status="publishing", updated_at=utcnow() - timedelta(hours=1))
        )
        await s.commit()

    db_call(client, stick)
    run_scheduler(client)
    [item] = client.get("/publications").json()
    assert item["status"] == "failed" and "interrupted" in item["error"]


def test_publications_are_private(client, run):
    account = connect(client, "linkedin")
    pub = publish(client, draft(run, "linkedin"), account["id"], scheduled_at=(utcnow() + timedelta(hours=1)).isoformat()).json()
    client.post("/auth/logout")
    client.post("/auth/register", json={"name": "B", "email": "b@example.com", "password": "another long password"})
    assert client.get("/publications").json() == []
    assert client.post(f"/publications/{pub['id']}/cancel").status_code == 404
    assert client.delete(f"/connections/{account['id']}").status_code == 404
