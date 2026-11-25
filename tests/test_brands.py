from backend.agents.graph import build_graph
from backend.api.deps import graph_dep
from backend.main import app
from backend.schemas import ContentPlan
from backend.services.fakes import FakeLLM, FakeSearcher
from tests.conftest import stream
from tests.test_api import BRAND


def make_brand(client, name="Data Coach"):
    res = client.post("/brands", json={"name": name, "input": BRAND})
    assert res.status_code == 201
    return res.json()


def run_stream(client, brand_id, **body):
    return stream(client, f"/brands/{brand_id}/runs/stream", {"platforms": ["linkedin", "x"], **body})


def test_brand_crud(client):
    b = make_brand(client)
    assert b["profile"] is None
    assert [x["id"] for x in client.get("/brands").json()] == [b["id"]]

    renamed = client.patch(f"/brands/{b['id']}", json={"name": "Renamed"}).json()
    assert renamed["name"] == "Renamed" and renamed["input"] == {**BRAND, "past_posts": ""}

    assert client.delete(f"/brands/{b['id']}").status_code == 204
    assert client.get(f"/brands/{b['id']}").status_code == 404


def test_streamed_run_is_saved_with_profile_and_drafts(client):
    b = make_brand(client)
    events = run_stream(client, b["id"], variants=2)

    kinds = [k for k, _ in events]
    assert kinds[0] == "run" and kinds[-1] == "result"
    run_id = events[0][1]["run_id"]
    result = events[-1][1]
    assert result["id"] == run_id and result["status"] == "completed"
    assert [r["platform"] for r in result["results"]] == ["linkedin", "x"]
    assert all(len(r["drafts"]) == len(r["items"]) == 2 for r in result["results"])

    # profile was stored on the brand
    assert client.get(f"/brands/{b['id']}").json()["profile"]["positioning"]

    # history + detail
    history = client.get(f"/brands/{b['id']}/runs").json()
    assert len(history) == 1
    assert history[0]["angle"] and history[0]["approved"] == 2
    detail = client.get(f"/runs/{run_id}").json()
    assert detail["results"] == result["results"]
    assert detail["sources"] and detail["plan"]["angle"]


def test_saved_profile_is_reused_unless_regenerate(client, llm):
    b = make_brand(client)
    run_stream(client, b["id"])
    run_stream(client, b["id"])
    assert llm.calls["BrandProfile"] == 1
    run_stream(client, b["id"], regenerate_profile=True)
    assert llm.calls["BrandProfile"] == 2


def test_changing_input_clears_profile(client):
    b = make_brand(client)
    run_stream(client, b["id"])
    same = client.patch(f"/brands/{b['id']}", json={"input": BRAND}).json()
    assert same["profile"] is not None
    changed = client.patch(f"/brands/{b['id']}", json={"input": {**BRAND, "expertise": "Data engineering"}}).json()
    assert changed["profile"] is None


def test_profile_can_be_edited(client, llm):
    b = make_brand(client)
    run_stream(client, b["id"])
    profile = client.get(f"/brands/{b['id']}").json()["profile"]
    profile["positioning"] = "Hand-written positioning"
    assert client.put(f"/brands/{b['id']}/profile", json=profile).status_code == 200
    result = run_stream(client, b["id"])[-1][1]
    assert result["brand_profile"]["positioning"] == "Hand-written positioning"
    assert llm.calls["BrandProfile"] == 1


def test_failed_run_is_recorded(client):
    class BrokenPlanner(FakeLLM):
        async def structured(self, schema, system, user, *, role="writer"):
            if schema is ContentPlan:
                raise RuntimeError("model unavailable")
            return await super().structured(schema, system, user, role=role)

    app.dependency_overrides[graph_dep] = lambda: build_graph(BrokenPlanner(), FakeSearcher())
    b = make_brand(client)
    events = run_stream(client, b["id"])
    assert events[-1][0] == "error" and "model unavailable" in events[-1][1]["detail"]
    run = client.get(f"/brands/{b['id']}/runs").json()[0]
    assert run["status"] == "failed" and run["finished_at"]


def test_non_streaming_brand_run_and_delete(client):
    b = make_brand(client)
    res = client.post(f"/brands/{b['id']}/runs", json={"platforms": ["medium"]})
    assert res.status_code == 201
    run_id = res.json()["id"]
    assert client.delete(f"/runs/{run_id}").status_code == 204
    assert client.get(f"/runs/{run_id}").status_code == 404


def test_deleting_brand_deletes_its_runs(client):
    b = make_brand(client)
    run_id = run_stream(client, b["id"])[0][1]["run_id"]
    client.delete(f"/brands/{b['id']}")
    assert client.get(f"/runs/{run_id}").status_code == 404


def test_unknown_ids_404(client):
    assert client.get("/brands/nope").status_code == 404
    assert client.get("/runs/nope").status_code == 404
    assert client.post("/brands/nope/runs/stream", json={"platforms": ["x"]}).status_code == 404


def test_timestamps_are_utc_aware(client):
    """SQLite drops tzinfo; the API must still return explicit UTC so browsers don't shift times."""
    b = make_brand(client)
    run_stream(client, b["id"])
    brand = client.get(f"/brands/{b['id']}").json()
    run = client.get(f"/brands/{b['id']}/runs").json()[0]
    for value in (brand["created_at"], brand["profile_updated_at"], run["created_at"], run["finished_at"]):
        assert value.endswith(("Z", "+00:00")), value
