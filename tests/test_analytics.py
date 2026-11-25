"""Step 9: post stats, results typed in by hand, the calendar range, and learning from what worked."""

from datetime import timedelta

import httpx
import pytest

from backend.db.models import utcnow
from backend.publishing.base import Credentials, MetricsUnavailable
from backend.publishing.linkedin import LinkedInClient
from backend.publishing.meta import InstagramClient, ThreadsClient
from backend.publishing.x import XClient
from tests.conftest import stream
from tests.test_adapters import SETTINGS, Recorder, query
from tests.test_brands import make_brand
from tests.test_publishing import connect, draft, publish

PLATFORMS = ["linkedin", "x", "threads", "instagram", "medium"]


def collect(client, force=False):
    return client.portal.call(lambda: client.app.state.publisher.collect_metrics(force=force))


@pytest.fixture
def published(client):
    """A brand with a run whose LinkedIn, X and Threads drafts are published through connected accounts."""
    brand = make_brand(client)
    run = stream(client, f"/brands/{brand['id']}/runs/stream", {"platforms": PLATFORMS})[-1][1]
    pubs = {}
    for p in ("linkedin", "x", "threads"):
        pubs[p] = publish(client, draft(run, p), connect(client, p)["id"]).json()
    return {"brand": brand, "run": run, "pubs": pubs}


def test_stats_are_collected_and_linkedin_asks_for_manual_entry(client, published):
    updated, failed = collect(client)
    assert (updated, failed) == (2, 1)
    posts = {p["platform"]: p for p in client.get("/analytics/posts").json()}
    assert posts["x"]["metrics"]["views"] > 0 and posts["x"]["metrics"]["engagement_rate"] > 0
    assert posts["x"]["pillar"] == "ML mistakes" and posts["x"]["brand_name"] == "Data Coach"
    assert posts["linkedin"]["metrics"] is None and "Add the numbers yourself" in posts["linkedin"]["metrics_error"]
    # not due again right away
    assert collect(client) == (0, 0)


def test_refresh_keeps_history(client, published):
    collect(client)
    assert client.post("/analytics/refresh").json() == {"updated": 2, "failed": 1}
    history = client.get(f"/publications/{published['pubs']['x']['id']}/metrics").json()
    assert len(history) == 2 and history[1]["views"] > history[0]["views"]
    assert all(h["source"] == "api" for h in history)


def test_results_typed_in_by_hand(client, published):
    li = published["pubs"]["linkedin"]
    res = client.post(f"/publications/{li['id']}/metrics", json={"views": 1200, "likes": 40, "comments": 9, "shares": 3})
    m = res.json()["metrics"]
    assert m["interactions"] == 52 and m["engagement_rate"] == pytest.approx(52 / 1200, abs=1e-4)
    assert client.get(f"/publications/{li['id']}/metrics").json()[0]["source"] == "manual"
    assert client.post(f"/publications/{li['id']}/metrics", json={"likes": -1}).status_code == 422


def test_results_need_a_published_post(client, published):
    run = published["run"]
    later = publish(client, draft(run, "instagram"), connect(client, "instagram")["id"], scheduled_at=(utcnow() + timedelta(hours=2)).isoformat())
    # Instagram needs an image, so make one and schedule
    client.post(f"/drafts/{draft(run, 'instagram')}/images", json={})
    pub = publish(client, draft(run, "instagram"), connect(client, "instagram")["id"], scheduled_at=(utcnow() + timedelta(hours=2)).isoformat()).json()
    assert later.status_code == 422
    assert client.post(f"/publications/{pub['id']}/metrics", json={"likes": 1}).status_code == 409


def test_posted_it_myself(client, published):
    did = draft(published["run"], "medium")
    assert client.post(f"/drafts/{did}/manual-publication", json={"url": "javascript:alert(1)"}).status_code == 422
    future = (utcnow() + timedelta(days=1)).isoformat()
    assert client.post(f"/drafts/{did}/manual-publication", json={"published_at": future}).status_code == 422
    pub = client.post(f"/drafts/{did}/manual-publication", json={"url": "https://medium.com/@me/post-1"}).json()
    assert pub["status"] == "published" and pub["account_id"] is None and pub["external_url"].startswith("https://medium.com")
    client.post(f"/publications/{pub['id']}/metrics", json={"views": 300, "likes": 25})
    medium = next(p for p in client.get("/analytics/posts").json() if p["platform"] == "medium")
    assert medium["metrics"]["likes"] == 25
    assert collect(client, force=True)[0] == 2  # manual posts aren't polled (no account)


def test_analytics_filters_and_privacy(client, published):
    collect(client)
    assert {p["platform"] for p in client.get("/analytics/posts", params={"platform": "x"}).json()} == {"x"}
    other = make_brand(client, "Other brand")
    assert client.get("/analytics/posts", params={"brand_id": other["id"]}).json() == []
    pub_id = published["pubs"]["x"]["id"]
    client.post("/auth/logout")
    client.post("/auth/register", json={"name": "B", "email": "b@example.com", "password": "another long password"})
    assert client.get("/analytics/posts").json() == []
    assert client.get(f"/publications/{pub_id}/metrics").status_code == 404
    assert client.post(f"/publications/{pub_id}/metrics", json={"likes": 1}).status_code == 404


def test_calendar_range(client, published):
    run = published["run"]
    acc = connect(client, "threads")["id"]
    in3 = publish(client, draft(run, "threads"), acc, scheduled_at=(utcnow() + timedelta(days=3)).isoformat()).json()
    publish(client, draft(run, "threads"), acc, scheduled_at=(utcnow() + timedelta(days=40)).isoformat())
    start, end = (utcnow() + timedelta(days=1)).isoformat(), (utcnow() + timedelta(days=10)).isoformat()
    window = client.get("/publications", params={"start": start, "end": end}).json()
    assert [p["id"] for p in window] == [in3["id"]]


def test_next_run_learns_from_best_posts(client, published, llm):
    collect(client)
    brand_id = published["brand"]["id"]
    events = stream(client, f"/brands/{brand_id}/runs/stream", {"platforms": ["x", "linkedin"]})
    assert any(k == "progress" and d.get("stage") == "learning" for k, d in events)
    x_prompt = [u for name, _, u in llm.prompts if name == "XThreadDrafts"][-1]
    assert "<best_posts>" in x_prompt and "interactions" in x_prompt
    li_prompt = [u for name, _, u in llm.prompts if name == "LinkedInPostDrafts"][-1]
    assert "<best_posts>" not in li_prompt  # no LinkedIn numbers yet

    stream(client, f"/brands/{brand_id}/runs/stream", {"platforms": ["x"], "learn_from_results": False})
    assert "<best_posts>" not in [u for name, _, u in llm.prompts if name == "XThreadDrafts"][-1]


def test_topic_performance_reaches_the_planner(client, published, llm):
    from sqlalchemy import update

    from backend.db.models import Run
    from tests.test_auth import db_call

    # a second run on a different topic, published and measured
    brand_id = published["brand"]["id"]
    run2 = stream(client, f"/brands/{brand_id}/runs/stream", {"platforms": ["x"]})[-1][1]

    async def retopic(s):
        await s.execute(update(Run).where(Run.id == run2["id"]).values(plan={**run2["plan"], "pillar": "Data storytelling"}))
        await s.commit()

    db_call(client, retopic)
    publish(client, draft(run2, "x"), connect(client, "x")["id"])
    collect(client)
    stream(client, f"/brands/{brand_id}/runs/stream", {"platforms": ["x"]})
    planner = [u for name, _, u in llm.prompts if name == "ContentPlan"][-1]
    assert "How this brand's topics have performed" in planner and '"Data storytelling"' in planner


# --- real adapters, mocked network ------------------------------------------------


async def test_x_metrics_mapping():
    net = Recorder({("GET", "/2/tweets/100"): lambda r: httpx.Response(200, json={"data": {"id": "100", "public_metrics": {
        "impression_count": 5000, "like_count": 120, "reply_count": 14, "retweet_count": 9, "quote_count": 2, "bookmark_count": 30}}})})
    m = await XClient(SETTINGS, net.transport()).fetch_metrics(Credentials("tok", "u"), "100")
    assert (m.views, m.likes, m.comments, m.shares, m.saves) == (5000, 120, 14, 11, 30)
    assert query(net.calls[0])["tweet.fields"] == "public_metrics"


async def test_threads_insights_both_shapes():
    body = {"data": [
        {"name": "views", "values": [{"value": 800}]},
        {"name": "likes", "total_value": {"value": 40}},
        {"name": "replies", "values": [{"value": 6}]},
        {"name": "reposts", "values": [{"value": 3}]},
        {"name": "quotes", "values": [{"value": 1}]},
        {"name": "shares", "values": [{"value": 2}]},
    ]}
    net = Recorder({("GET", "/m1/insights"): lambda r: httpx.Response(200, json=body)})
    m = await ThreadsClient(SETTINGS, net.transport()).fetch_metrics(Credentials("tok", "u"), "m1")
    assert (m.views, m.likes, m.comments, m.shares) == (800, 40, 6, 6)
    assert "threads_manage_insights" in ThreadsClient.scopes


async def test_instagram_falls_back_to_basic_counts():
    net = Recorder({
        ("GET", "/M1/insights"): lambda r: httpx.Response(400, json={"error": {"message": "Not enough followers"}}),
        ("GET", "/M1"): lambda r: httpx.Response(200, json={"like_count": 55, "comments_count": 7}),
    })
    m = await InstagramClient(SETTINGS, net.transport()).fetch_metrics(Credentials("tok", "u"), "M1")
    assert (m.likes, m.comments, m.views) == (55, 7, None)

    net = Recorder({
        ("GET", "/M1/insights"): lambda r: httpx.Response(200, json={"data": [
            {"name": "views", "values": [{"value": 2400}]}, {"name": "reach", "values": [{"value": 1900}]},
            {"name": "shares", "values": [{"value": 12}]}, {"name": "saved", "values": [{"value": 31}]}]}),
        ("GET", "/M1"): lambda r: httpx.Response(200, json={"like_count": 55, "comments_count": 7}),
    })
    m = await InstagramClient(SETTINGS, net.transport()).fetch_metrics(Credentials("tok", "u"), "M1")
    assert (m.views, m.reach, m.shares, m.saves) == (2400, 1900, 12, 31)


async def test_linkedin_has_no_stats_api():
    with pytest.raises(MetricsUnavailable):
        await LinkedInClient(SETTINGS).fetch_metrics(Credentials("tok", "u"), "urn:li:share:1")
