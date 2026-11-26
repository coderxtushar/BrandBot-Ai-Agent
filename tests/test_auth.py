"""Accounts, sessions, and keeping each user's data private."""

from sqlalchemy import select

from backend.db.models import Brand, Session
from tests.conftest import USER, sign_up, stream
from tests.test_brands import make_brand


def db_call(client, fn):
    """Run an async function against the app's database inside the test server's event loop."""
    db = client.app.state.publisher.db

    async def go():
        async with db.sessions() as s:
            return await fn(s)

    return client.portal.call(go)


def test_sign_up_sign_in_and_out(anon_client):
    c = anon_client
    assert c.get("/auth/me").status_code == 401
    me = sign_up(c)
    assert me["email"] == USER["email"] and "password" not in str(me)
    assert c.get("/auth/me").json()["id"] == me["id"]

    assert c.post("/auth/logout").status_code == 204
    assert c.get("/auth/me").status_code == 401

    bad = c.post("/auth/login", json={"email": USER["email"], "password": "wrong password!!"})
    assert bad.status_code == 401 and "don't match" in bad.json()["detail"]
    ok = c.post("/auth/login", json={"email": USER["email"].upper(), "password": USER["password"]})
    assert ok.status_code == 200 and c.get("/auth/me").status_code == 200


def test_sign_up_validation(anon_client):
    c = anon_client
    assert c.post("/auth/register", json={**USER, "password": "short"}).status_code == 422
    assert c.post("/auth/register", json={**USER, "email": "not-an-email"}).status_code == 422
    sign_up(c)
    dup = c.post("/auth/register", json={**USER, "email": USER["email"].upper()})
    assert dup.status_code == 409


def test_unknown_email_and_wrong_password_look_the_same(anon_client):
    c = anon_client
    sign_up(c)
    a = c.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    b = c.post("/auth/login", json={"email": USER["email"], "password": "whatever123"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_login_is_rate_limited(anon_client):
    c = anon_client
    codes = [c.post("/auth/login", json={"email": "x@example.com", "password": "nope-nope-nope"}).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_sessions_are_stored_hashed(client):
    token = client.cookies.get("bb_session")
    hashes = db_call(client, lambda s: s.scalars(select(Session.token_hash)))
    stored = list(hashes)
    assert stored and token not in stored


def test_everything_needs_sign_in(anon_client):
    c = anon_client
    for method, path in [
        ("get", "/brands"),
        ("post", "/runs"),
        ("get", "/runs/x"),
        ("get", "/drafts/x"),
        ("delete", "/images/x"),
        ("get", "/connections"),
        ("get", "/publications"),
    ]:
        assert getattr(c, method)(path).status_code in (401, 422), path
    assert c.get("/brands").status_code == 401


def test_users_cannot_see_each_others_work(client):
    brand = make_brand(client)
    run = stream(client, f"/brands/{brand['id']}/runs/stream", {"platforms": ["linkedin"]})[-1][1]
    draft_id = run["results"][0]["drafts"][0]["id"]
    image = client.post(f"/drafts/{draft_id}/images", json={}).json()

    client.post("/auth/logout")
    sign_up(client, email="other@example.com")
    assert client.get("/brands").json() == []
    for method, path in [
        ("get", f"/brands/{brand['id']}"),
        ("patch", f"/brands/{brand['id']}"),
        ("delete", f"/brands/{brand['id']}"),
        ("get", f"/brands/{brand['id']}/runs"),
        ("get", f"/runs/{run['id']}"),
        ("delete", f"/runs/{run['id']}"),
        ("get", f"/drafts/{draft_id}"),
        ("post", f"/drafts/{draft_id}/rewrite"),
        ("post", f"/drafts/{draft_id}/images"),
        ("delete", f"/images/{image['id']}"),
    ]:
        kwargs = {"json": {"preset": "shorter"}} if method in ("post", "patch") else {}
        assert getattr(client, method)(path, **kwargs).status_code == 404, (method, path)
    assert client.post(f"/brands/{brand['id']}/runs/stream", json={"platforms": ["x"]}).status_code == 404


def test_first_account_adopts_existing_brands(anon_client):
    c = anon_client

    async def orphan(s):
        s.add(Brand(name="Made before accounts", input={"target_audience": "Founders", "expertise": "Sales", "tone_of_voice": "Warm", "content_pillars": "Hiring", "past_posts": ""}))
        await s.commit()

    db_call(c, orphan)
    sign_up(c)
    assert [b["name"] for b in c.get("/brands").json()] == ["Made before accounts"]
    c.post("/auth/logout")
    sign_up(c, email="second@example.com")
    assert c.get("/brands").json() == []


def test_requests_from_other_sites_are_rejected(client):
    evil = client.post("/brands", json={"name": "x", "input": {}}, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    ours = client.post(
        "/brands",
        json={"name": "Mine", "input": {"target_audience": "aaa", "expertise": "bbb", "tone_of_voice": "ccc", "content_pillars": "ddd"}},
        headers={"Origin": "http://localhost:3000"},
    )
    assert ours.status_code == 201


def test_media_stays_public_for_platforms_to_fetch(client):
    """Instagram and Threads download images by URL, so media is served without a session (random URLs)."""
    brand = make_brand(client)
    run = stream(client, f"/brands/{brand['id']}/runs/stream", {"platforms": ["instagram"]})[-1][1]
    img = client.post(f"/drafts/{run['results'][0]['drafts'][0]['id']}/images", json={}).json()
    client.post("/auth/logout")
    assert client.get(img["url"]).status_code == 200


# --- changing the password ------------------------------------------------------


NEW = "a much better passphrase"


def change(c, current=USER["password"], new=NEW):
    return c.post("/auth/password", json={"current_password": current, "new_password": new})


def test_change_password_signs_out_other_browsers(client):
    from fastapi.testclient import TestClient

    laptop = TestClient(client.app)  # the same account, signed in somewhere else
    assert laptop.post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 200

    res = change(client)
    assert res.status_code == 200 and res.json() == {"signed_out_sessions": 1}
    assert client.get("/auth/me").status_code == 200  # this browser stays signed in
    assert laptop.get("/auth/me").status_code == 401  # the other one is out

    client.post("/auth/logout")
    assert client.post("/auth/login", json={"email": USER["email"], "password": USER["password"]}).status_code == 401
    assert client.post("/auth/login", json={"email": USER["email"], "password": NEW}).status_code == 200


def test_change_password_needs_the_current_one(client):
    res = change(client, current="not my password")
    assert res.status_code == 400 and "current password" in res.json()["detail"]
    assert client.get("/auth/me").status_code == 200  # a typo doesn't sign you out
    assert change(client, new="short").status_code == 422  # same rules as sign-up
    same = change(client, new=USER["password"])
    assert same.status_code == 400 and "different" in same.json()["detail"]


def test_change_password_needs_sign_in(anon_client):
    assert change(anon_client).status_code == 401


def test_change_password_is_rate_limited(client, monkeypatch):
    from backend.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_login", "2/hour")
    for _ in range(2):
        assert change(client, current="wrong guess").status_code == 400
    assert change(client).status_code == 429  # even the right password waits now
