"""Human-in-the-loop: a run pauses after research, the author edits the plan, and the run resumes."""

from fastapi.testclient import TestClient

from backend.agents.checkpoint import open_checkpointer
from backend.config import Settings
from backend.db.session import Database, get_database
from backend.main import app
from backend.services.fakes import FakeLLM
from tests.conftest import stream, use_services
from tests.test_brands import make_brand

PLATFORMS = ["linkedin", "x"]


def start_paused(client, brand_id):
    events = stream(client, f"/brands/{brand_id}/runs/stream", {"platforms": PLATFORMS, "review_plan": True})
    assert events[-1][0] == "awaiting", events[-1]
    return events


def test_run_pauses_before_writing(client, llm):
    b = make_brand(client)
    events = start_paused(client, b["id"])
    paused = events[-1][1]
    assert paused["status"] == "awaiting_plan"
    assert paused["plan"]["angle"] and len(paused["sources"]) == 3 and paused["results"] == []
    stages = {d.get("stage") for k, d in events if k == "progress"}
    assert "writing" not in stages
    assert not any("Drafts" in name for name, *_ in llm.prompts)  # no content written yet
    assert client.get(f"/brands/{b['id']}/runs").json()[0]["status"] == "awaiting_plan"
    # the profile is saved even though the run is paused
    assert client.get(f"/brands/{b['id']}").json()["profile"] is not None


def test_resume_with_edited_plan(client, llm):
    b = make_brand(client)
    paused = start_paused(client, b["id"])[-1][1]
    keep = paused["sources"][0]["url"]
    decision = {"angle": "Executives ignore models they can't explain", "source_urls": [keep], "guidance": "Mention SHAP"}

    events = stream(client, f"/runs/{paused['id']}/resume/stream", decision)
    assert events[0] == ("run", {"run_id": paused["id"]})
    kind, result = events[-1]
    assert kind == "result" and result["status"] == "completed"
    assert result["plan"]["angle"] == decision["angle"]
    assert [s["url"] for s in result["sources"]] == [keep]
    assert [r["platform"] for r in result["results"]] == PLATFORMS

    writer_prompts = [u for name, _, u in llm.prompts if name.endswith("Drafts")]
    assert writer_prompts and all(decision["angle"] in u and "Mention SHAP" in u for u in writer_prompts)
    assert llm.calls["ContentPlan"] == 1  # planning was not redone

    # can't resume twice
    assert client.post(f"/runs/{paused['id']}/resume/stream", json={}).status_code == 409


def test_resume_without_changes_keeps_plan(client):
    b = make_brand(client)
    paused = start_paused(client, b["id"])[-1][1]
    result = stream(client, f"/runs/{paused['id']}/resume/stream", {})[-1][1]
    assert result["plan"]["angle"] == paused["plan"]["angle"]
    assert len(result["sources"]) == len(paused["sources"])


def test_cancel_paused_run(client):
    b = make_brand(client)
    paused = start_paused(client, b["id"])[-1][1]
    res = client.post(f"/runs/{paused['id']}/cancel")
    assert res.status_code == 200 and res.json()["status"] == "cancelled"
    assert client.post(f"/runs/{paused['id']}/resume/stream", json={}).status_code == 409
    assert client.post(f"/runs/{paused['id']}/cancel").status_code == 409


def test_completed_run_cannot_be_resumed(client):
    b = make_brand(client)
    done = stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": ["x"]})[-1][1]
    assert client.post(f"/runs/{done['id']}/resume/stream", json={}).status_code == 409


def test_non_streaming_run_can_pause(client):
    b = make_brand(client)
    res = client.post(f"/brands/{b['id']}/runs", json={"platforms": ["x"], "review_plan": True})
    assert res.status_code == 201 and res.json()["status"] == "awaiting_plan"
    assert client.delete(f"/runs/{res.json()['id']}").status_code == 204


def test_paused_run_survives_restart(tmp_path):
    """Pause with one server process, resume with a fresh one: the checkpoint lives on disk."""
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'app.db'}"
    settings = Settings(database_url=db_url, checkpoint_db=str(tmp_path / "checkpoints.db"))

    def boot():
        app.dependency_overrides[get_database] = lambda: Database(db_url)
        app.dependency_overrides[open_checkpointer] = lambda: open_checkpointer(settings)
        use_services(FakeLLM())
        return TestClient(app)

    try:
        with boot() as first:
            b = make_brand(first)
            paused = start_paused(first, b["id"])[-1][1]
        app.dependency_overrides.clear()

        with boot() as second:  # "restarted" server: new app state, new services, new graph
            result = stream(second, f"/runs/{paused['id']}/resume/stream", {"angle": "After restart"})[-1][1]
        assert result["status"] == "completed" and result["plan"]["angle"] == "After restart"
    finally:
        app.dependency_overrides.clear()
