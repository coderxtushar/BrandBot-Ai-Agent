"""Production readiness: startup checks, rate limits, cron tick, health, request ids, cloud storage, tracing."""

import json
import logging
import os
from datetime import UTC, datetime, timedelta

import pytest

from backend.config import Settings, get_settings
from backend.observability import JsonFormatter, client_ip, configure_tracing, request_id, trace_config
from backend.ratelimit import Rule, parse_rules
from backend.services.storage import DbMediaStorage, GcsMediaStorage, valid_key
from tests.conftest import USER, sign_up, stream
from tests.test_brands import make_brand
from tests.test_publishing import connect, draft, publish, set_due


@pytest.fixture
def limits(monkeypatch):
    """Set a rate limit for one test: limits(rate_limit_runs="2/hour")."""
    s = get_settings()

    def apply(**values):
        for k, v in values.items():
            monkeypatch.setattr(s, k, v)

    return apply


# --- settings -----------------------------------------------------------------


def test_production_refuses_unsafe_settings():
    errors, warnings = Settings(environment="production", _env_file=None).deployment_problems()
    assert any("SECRET_KEY" in e for e in errors) and any("COOKIE_SECURE" in e for e in errors)
    assert any("SQLite" in w for w in warnings) and any("MEDIA_BACKEND" in w for w in warnings)


def test_production_settings_that_pass():
    s = Settings(
        _env_file=None,
        environment="production",
        secret_key="x" * 48,
        cookie_secure=True,
        database_url="postgresql+asyncpg://u:p@db/brandbot",
        media_backend="gcs",
        gcs_bucket="bucket",
        scheduler_enabled=False,
        cron_secret="tick-secret",
        api_public_url="https://app.example.com/api",
        web_url="https://app.example.com",
        cors_origins=["https://app.example.com"],
    )
    assert s.deployment_problems() == ([], [])


# --- rate limits ----------------------------------------------------------------


@pytest.mark.parametrize(
    "spec, rules",
    [
        ("10/hour", (Rule(10, 3600),)),
        ("10/hour, 40/day", (Rule(10, 3600), Rule(40, 86400))),
        ("10/5minutes", (Rule(10, 300),)),
        ("3 / 30 seconds", (Rule(3, 30),)),
        ("", ()),
    ],
)
def test_parse_rules(spec, rules):
    assert parse_rules(spec) == rules


@pytest.mark.parametrize("spec", ["ten/hour", "10/fortnight", "10"])
def test_bad_rules_fail_loudly(spec):
    with pytest.raises(ValueError):
        parse_rules(spec)


def test_rule_period_reads_naturally():
    assert Rule(1, 3600).period == "hour" and Rule(1, 300).period == "5 minutes" and Rule(1, 86400 * 2).period == "2 days"


def test_runs_are_limited_per_user(client, limits):
    limits(rate_limit_runs="2/hour")
    b = make_brand(client)
    for _ in range(2):
        assert stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": ["x"]})[-1][0] == "result"
    res = client.post(f"/brands/{b['id']}/runs/stream", json={"platforms": ["x"]})
    assert res.status_code == 429
    assert "limit of 2 AI runs per hour" in res.json()["detail"]
    assert 0 < int(res.headers["retry-after"]) <= 3600

    # someone else isn't affected
    client.post("/auth/logout")
    sign_up(client, email="other@example.com")
    b2 = make_brand(client)
    assert stream(client, f"/brands/{b2['id']}/runs/stream", {"platforms": ["x"]})[-1][0] == "result"


def test_images_and_rewrites_have_their_own_limits(client, limits):
    limits(rate_limit_images="1/day", rate_limit_rewrites="1/hour")
    b = make_brand(client)
    run = stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": ["linkedin"]})[-1][1]
    d = draft(run, "linkedin")
    assert client.post(f"/drafts/{d}/images", json={}).status_code == 201
    assert client.post(f"/drafts/{d}/images", json={}).status_code == 429
    assert client.post(f"/drafts/{d}/rewrite", json={"preset": "shorter"}).status_code == 200
    second = client.post(f"/drafts/{d}/rewrite", json={"preset": "shorter"})
    assert second.status_code == 429 and "AI rewrites" in second.json()["detail"]


def test_limits_can_be_switched_off(client, limits):
    limits(rate_limit_runs="1/hour", rate_limits_enabled=False)
    b = make_brand(client)
    for _ in range(2):
        assert stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": ["x"]})[-1][0] == "result"


def test_signups_are_limited_per_ip(anon_client, limits):
    limits(rate_limit_signup="2/hour")
    for i in range(2):
        sign_up(anon_client, email=f"u{i}@example.com")
    res = anon_client.post("/auth/register", json={**USER, "email": "u3@example.com"})
    assert res.status_code == 429 and "new accounts" in res.json()["detail"]


def test_signup_limit_uses_the_forwarded_ip_behind_a_proxy(anon_client, limits):
    limits(rate_limit_signup="1/hour", trusted_proxy_hops=1)
    first = anon_client.post("/auth/register", json={**USER, "email": "a@example.com"}, headers={"X-Forwarded-For": "1.1.1.1"})
    other = anon_client.post("/auth/register", json={**USER, "email": "b@example.com"}, headers={"X-Forwarded-For": "2.2.2.2"})
    again = anon_client.post("/auth/register", json={**USER, "email": "c@example.com"}, headers={"X-Forwarded-For": "1.1.1.1"})
    assert (first.status_code, other.status_code, again.status_code) == (201, 201, 429)


def test_client_ip_ignores_what_the_client_wrote():
    h = {"x-forwarded-for": "6.6.6.6, 1.2.3.4, 10.0.0.1"}  # spoofed, real client, the first proxy
    assert client_ip(h, "10.0.0.2", 0) == "10.0.0.2"
    assert client_ip(h, "10.0.0.2", 1) == "10.0.0.1"
    assert client_ip(h, "10.0.0.2", 2) == "1.2.3.4"
    assert client_ip({}, "10.0.0.2", 2) == "10.0.0.2"  # header missing: fall back to the peer


# --- cron tick -------------------------------------------------------------------


def test_tick_needs_the_cron_secret(client, limits):
    assert client.post("/internal/tick").status_code == 404  # no secret configured: disabled
    limits(cron_secret="s3cret")
    assert client.post("/internal/tick").status_code == 404
    assert client.post("/internal/tick", headers={"Authorization": "Bearer wrong"}).status_code == 404
    assert client.post("/internal/tick", headers={"Authorization": "Bearer s3cret"}).status_code == 200


def test_tick_publishes_due_posts(client, limits, platforms):
    limits(cron_secret="s3cret")
    account = connect(client, "x")
    run = stream(client, f"/brands/{make_brand(client)['id']}/runs/stream", {"platforms": ["x"]})[-1][1]
    later = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    pub = publish(client, draft(run, "x"), account["id"], scheduled_at=later).json()
    set_due(client, pub["id"])

    res = client.post("/internal/tick", headers={"Authorization": "Bearer s3cret"})
    assert res.status_code == 200 and res.json()["published"] == 1
    assert len(platforms["x"].posts) == 1
    # a second tick finds nothing left to do
    assert client.post("/internal/tick", headers={"Authorization": "Bearer s3cret"}).json()["published"] == 0


def test_client_ip_check_shows_the_forwarded_chain(client, limits):
    assert client.get("/internal/client-ip").status_code == 404
    limits(cron_secret="s3cret", trusted_proxy_hops=1)
    res = client.get("/internal/client-ip", headers={"Authorization": "Bearer s3cret", "X-Forwarded-For": "9.9.9.9, 1.2.3.4"})
    assert res.json() == {"x_forwarded_for": "9.9.9.9, 1.2.3.4", "peer": "testclient", "trusted_proxy_hops": 1, "client_ip": "1.2.3.4"}


# --- health and request ids -------------------------------------------------------


def test_health_and_ready(anon_client):
    assert anon_client.get("/health").json() == {"status": "ok"}
    assert anon_client.get("/ready").json() == {"status": "ok", "database": "ok"}


def test_every_response_has_a_request_id(anon_client):
    generated = anon_client.get("/health").headers["x-request-id"]
    assert len(generated) == 32
    kept = anon_client.get("/health", headers={"X-Request-ID": "abc12345-trace"}).headers["x-request-id"]
    assert kept == "abc12345-trace"
    junk = anon_client.get("/health", headers={"X-Request-ID": "<script>"}).headers["x-request-id"]
    assert junk != "<script>"


def test_json_logs_for_cloud_logging():
    token = request_id.set("req-1")
    try:
        record = logging.LogRecord("brandbot", logging.WARNING, __file__, 1, "hello %s", ("world",), None)
        entry = json.loads(JsonFormatter("my-project").format(record))
    finally:
        request_id.reset(token)
    assert entry["severity"] == "WARNING" and entry["message"] == "hello world" and entry["request_id"] == "req-1"


# --- cloud storage -------------------------------------------------------------------


class FakeBlob:
    def __init__(self, store, name):
        self.store, self.name, self.cache_control = store, name, None

    def upload_from_string(self, data, content_type):
        self.store[self.name] = (data, content_type, self.cache_control)

    def download_as_bytes(self):
        from google.api_core.exceptions import NotFound

        if self.name not in self.store:
            raise NotFound("missing")
        return self.store[self.name][0]

    def delete(self):
        from google.api_core.exceptions import NotFound

        if self.store.pop(self.name, None) is None:
            raise NotFound("missing")


class FakeBucket:
    def __init__(self):
        self.objects = {}

    def blob(self, name):
        return FakeBlob(self.objects, name)


async def test_gcs_storage_round_trip():
    bucket = FakeBucket()
    storage = GcsMediaStorage("unused", bucket=bucket)
    key = await storage.save(b"png-bytes", "image/png")
    assert valid_key(key) and key.endswith(".png")
    assert bucket.objects[key][1:] == ("image/png", "public, max-age=31536000, immutable")
    assert await storage.read(key) == b"png-bytes"
    await storage.delete(key)
    await storage.delete(key)  # already gone: no error
    assert await storage.read(key) is None
    assert await storage.read("../secrets.txt") is None


def test_images_are_served_from_cloud_storage(client):
    from backend.api.deps import storage_dep

    storage = GcsMediaStorage("unused", bucket=FakeBucket())
    client.app.dependency_overrides[storage_dep] = lambda: storage
    run = stream(client, f"/brands/{make_brand(client)['id']}/runs/stream", {"platforms": ["linkedin"]})[-1][1]
    img = client.post(f"/drafts/{draft(run, 'linkedin')}/images", json={}).json()
    res = client.get(img["url"])
    assert res.status_code == 200 and res.content and res.headers["cache-control"].startswith("public")


def test_images_can_live_in_the_database(client):
    """MEDIA_BACKEND=db (Render's free disk is wiped on restart): images are stored, served and deleted with their run."""
    from sqlalchemy import func, select

    from backend.api.deps import storage_dep
    from backend.db.models import MediaObject
    from backend.db.session import get_database

    db = client.app.dependency_overrides[get_database]()
    client.app.dependency_overrides[storage_dep] = lambda: DbMediaStorage(db)

    async def stored():
        async with db.sessions() as s:
            return (await s.execute(select(func.count()).select_from(MediaObject))).scalar_one()

    run = stream(client, f"/brands/{make_brand(client)['id']}/runs/stream", {"platforms": ["linkedin"]})[-1][1]
    img = client.post(f"/drafts/{draft(run, 'linkedin')}/images", json={}).json()
    res = client.get(img["url"])
    assert res.status_code == 200 and res.content and res.headers["content-type"].startswith("image/")
    assert client.portal.call(stored) == 1

    assert client.delete(f"/runs/{run['id']}").status_code == 204
    assert client.portal.call(stored) == 0
    assert client.get(img["url"]).status_code == 404


async def test_db_storage_rejects_foreign_keys(tmp_path):
    from backend.db.session import Database

    db = Database(f"sqlite+aiosqlite:///{tmp_path / 'm.db'}")
    await db.create_all()
    storage = DbMediaStorage(db)
    key = await storage.save(b"bytes", "image/webp")
    assert key.endswith(".webp") and await storage.read(key) == b"bytes"
    assert await storage.read("../etc/passwd") is None
    await storage.delete("../etc/passwd")  # ignored, no error
    await db.dispose()


# --- tracing ---------------------------------------------------------------------------


def test_trace_config_names_and_tags_a_run():
    cfg = trace_config("brand run", user_id="u1", brand_id="b1", run_id="r1", platforms=["x", "linkedin"])
    assert cfg["run_name"] == "brand run" and cfg["tags"] == ["x", "linkedin"]
    assert cfg["metadata"] == {"user_id": "u1", "brand_id": "b1", "run_id": "r1"}


def test_tracing_exports_langsmith_env(monkeypatch):
    for k in ("LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT", "LANGSMITH_ENDPOINT"):
        monkeypatch.delenv(k, raising=False)  # restored (removed) after the test
    assert configure_tracing(Settings(_env_file=None)) is False
    assert configure_tracing(Settings(_env_file=None, langsmith_tracing=True)) is False  # no key

    on = Settings(_env_file=None, langsmith_tracing=True, langsmith_api_key="lsv2-key", langsmith_project="bb-prod")
    assert configure_tracing(on) is True
    assert os.environ["LANGSMITH_TRACING"] == "true" and os.environ["LANGSMITH_PROJECT"] == "bb-prod"


# --- database urls ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "pasted, sqlalchemy, libpq",
    [
        (  # Neon, copied from the console
            "postgresql://u:p%40ss@ep-x.ap-south-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+asyncpg://u:p%40ss@ep-x.ap-south-1.aws.neon.tech/neondb?ssl=require",
            "postgresql://u:p%40ss@ep-x.ap-south-1.aws.neon.tech/neondb?sslmode=require",
        ),
        ("postgres://u:p@db:5432/bb", "postgresql+asyncpg://u:p@db:5432/bb", "postgresql://u:p@db:5432/bb"),
        (
            "postgresql+asyncpg://u:p@/bb?host=/cloudsql/p:r:i",
            "postgresql+asyncpg://u:p@/bb?host=%2Fcloudsql%2Fp%3Ar%3Ai",
            "postgresql://u:p@/bb?host=%2Fcloudsql%2Fp%3Ar%3Ai",
        ),
        ("sqlite+aiosqlite:///./brandbot.db", "sqlite+aiosqlite:///./brandbot.db", None),
    ],
)
def test_database_urls_work_as_hosts_print_them(pasted, sqlalchemy, libpq):
    from backend.agents.checkpoint import _postgres_dsn

    url = Settings(_env_file=None, database_url=pasted).database_url
    assert url == sqlalchemy
    if libpq:
        assert _postgres_dsn(url) == libpq
