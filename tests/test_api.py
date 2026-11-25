import json

import pytest
from fastapi.testclient import TestClient

from backend.agents.graph import build_graph
from backend.main import _graph_dep, app
from backend.services.fakes import FakeLLM, FakeSearcher

PAYLOAD = {
    "brand": {
        "target_audience": "Junior data scientists",
        "expertise": "ML and Tableau",
        "tone_of_voice": "Clear, practical",
        "content_pillars": "ML mistakes, data storytelling",
    },
    "platforms": ["x", "linkedin", "medium"],
    "variants": 2,
}


@pytest.fixture
def client():
    app.dependency_overrides[_graph_dep] = lambda: build_graph(FakeLLM(), FakeSearcher())
    yield TestClient(app)
    app.dependency_overrides.clear()


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
    bad = {**PAYLOAD, "platforms": ["myspace"]}
    assert client.post("/runs", json=bad).status_code == 422


def test_stream_emits_progress_then_result(client):
    with client.stream("POST", "/runs/stream", json=PAYLOAD) as res:
        raw = "".join(res.iter_text())
    events = [
        (block.split("event: ")[1].split("\r\n")[0], json.loads(block.split("data: ", 1)[1]))
        for block in raw.split("\r\n\r\n")
        if "event: " in block
    ]
    kinds = [k for k, _ in events]
    assert kinds[-1] == "result" and "progress" in kinds
    stages = {d.get("stage") for k, d in events if k == "progress"}
    assert {"profile", "planning", "research", "writing", "reviewing", "done"} <= stages
    assert len(events[-1][1]["results"]) == 3


def test_missing_keys_give_503(monkeypatch):
    from backend import main

    def boom():
        raise RuntimeError("GOOGLE_API_KEY is not set.")

    monkeypatch.setattr(main, "get_graph", boom)
    assert TestClient(app).post("/runs", json=PAYLOAD).status_code == 503
