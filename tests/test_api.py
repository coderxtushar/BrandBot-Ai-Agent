from fastapi.testclient import TestClient

from backend.main import app
from tests.conftest import stream

BRAND = {
    "target_audience": "Junior data scientists",
    "expertise": "ML and Tableau",
    "tone_of_voice": "Clear, practical",
    "content_pillars": "ML mistakes, data storytelling",
}
PAYLOAD = {"brand": BRAND, "platforms": ["x", "linkedin", "medium"], "variants": 2}


def test_platforms(client):
    ids = [p["id"] for p in client.get("/platforms").json()]
    assert ids == ["linkedin", "x", "threads", "instagram", "medium", "youtube_shorts"]


def test_run_returns_results_in_requested_order(client):
    res = client.post("/runs", json=PAYLOAD)
    assert res.status_code == 200
    body = res.json()
    assert [r["platform"] for r in body["results"]] == ["x", "linkedin", "medium"]
    assert body["brand_profile"]["pillars"]
    assert len(body["results"][0]["items"]) == 2


def test_validation_rejects_unknown_platform(client):
    assert client.post("/runs", json={**PAYLOAD, "platforms": ["myspace"]}).status_code == 422


def test_stream_emits_progress_then_result(client):
    events = stream(client, "/runs/stream", PAYLOAD)
    kinds = [k for k, _ in events]
    assert kinds[-1] == "result" and "progress" in kinds
    stages = {d.get("stage") for k, d in events if k == "progress"}
    assert {"profile", "planning", "research", "writing", "reviewing", "done"} <= stages
    assert len(events[-1][1]["results"]) == 3


def test_missing_keys_give_503(monkeypatch, tmp_path):
    from backend.agents.checkpoint import open_checkpointer
    from backend.api import deps
    from backend.db.session import Database, get_database
    from tests.conftest import memory_checkpointer

    def boom():
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    monkeypatch.setattr(deps, "get_services", boom)
    app.dependency_overrides[get_database] = lambda: Database(f"sqlite+aiosqlite:///{tmp_path / 'x.db'}")
    app.dependency_overrides[open_checkpointer] = memory_checkpointer
    try:
        with TestClient(app) as c:
            assert c.post("/runs", json=PAYLOAD).status_code == 503
    finally:
        app.dependency_overrides.clear()
