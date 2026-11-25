"""The editing loop: edit, approve, AI rewrite, regenerate, and version history."""

import pytest

from tests.conftest import stream
from tests.test_brands import make_brand


@pytest.fixture
def run(client):
    b = make_brand(client)
    return stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": ["linkedin", "x"]})[-1][1]


def draft_id(run, platform, i=0):
    return next(r for r in run["results"] if r["platform"] == platform)["drafts"][i]["id"]


def versions(client, did):
    return client.get(f"/drafts/{did}/versions").json()


def test_get_draft(client, run):
    d = client.get(f"/drafts/{draft_id(run, 'linkedin')}").json()
    assert d["platform"] == "linkedin" and d["run_id"] == run["id"]
    assert d["content"]["hook"] and d["text"].startswith(d["content"]["hook"])
    assert d["status"] == "draft" and d["lint"] == []
    assert [v["source"] for v in versions(client, d["id"])] == ["generated"]


def test_manual_edit_rerenders_and_records_version(client, run):
    did = draft_id(run, "linkedin")
    content = client.get(f"/drafts/{did}").json()["content"]
    content["hook"] = "A brand new hook."
    d = client.patch(f"/drafts/{did}", json={"content": content}).json()
    assert d["text"].startswith("A brand new hook.")
    assert [v["source"] for v in versions(client, did)] == ["edited", "generated"]
    # the saved run reflects the edit
    saved = client.get(f"/runs/{run['id']}").json()
    assert saved["results"][0]["items"][0]["hook"] == "A brand new hook."


def test_edit_is_validated_against_platform(client, run):
    did = draft_id(run, "x")
    assert client.patch(f"/drafts/{did}", json={"content": {"hook": "wrong shape"}}).status_code == 422


def test_edit_reports_lint_problems(client, run):
    did = draft_id(run, "x")
    d = client.patch(f"/drafts/{did}", json={"content": {"tweets": ["x" * 300], "hashtags": []}}).json()
    assert any("280" in issue for issue in d["lint"])
    saved = client.get(f"/runs/{run['id']}").json()
    x = next(r for r in saved["results"] if r["platform"] == "x")
    assert any("280" in issue for issue in x["drafts"][0]["lint"])


def test_approve_and_edit_resets_approval(client, run):
    did = draft_id(run, "linkedin")
    assert client.patch(f"/drafts/{did}", json={"status": "approved"}).json()["status"] == "approved"
    saved = client.get(f"/runs/{run['id']}").json()
    assert saved["results"][0]["drafts"][0]["status"] == "approved"

    content = client.get(f"/drafts/{did}").json()["content"]
    content["body"] = "Changed after approval."
    assert client.patch(f"/drafts/{did}", json={"content": content}).json()["status"] == "draft"


def test_rewrite_with_preset_and_instruction(client, run, llm):
    did = draft_id(run, "linkedin")
    d = client.post(f"/drafts/{did}/rewrite", json={"preset": "shorter", "instruction": "Mention our launch"}).json()
    assert d["content"]["hook"].endswith("[rewritten]")
    assert d["review"] and d["review"]["approved"]
    prompt = [u for name, _, u in llm.prompts if name == "LinkedInPostDrafts"][-1]
    assert "noticeably shorter" in prompt and "Mention our launch" in prompt and "current LinkedIn draft" in prompt
    latest = versions(client, did)[0]
    assert latest["source"] == "rewrite" and "Mention our launch" in latest["note"]
    # the review is shown per draft in the run
    saved = client.get(f"/runs/{run['id']}").json()
    assert saved["results"][0]["drafts"][0]["review"]["score"] == 9


def test_fresh_draft(client, run):
    did = draft_id(run, "x")
    d = client.post(f"/drafts/{did}/rewrite", json={"fresh": True, "instruction": "Make it about hiring"}).json()
    assert d["content"]["tweets"][0].endswith("[guided]")
    assert versions(client, did)[0]["source"] == "regenerate"


def test_rewrite_needs_some_instruction(client, run):
    assert client.post(f"/drafts/{draft_id(run, 'x')}/rewrite", json={}).status_code == 422


def test_restore_version(client, run):
    did = draft_id(run, "linkedin")
    original = client.get(f"/drafts/{did}").json()
    client.post(f"/drafts/{did}/rewrite", json={"preset": "punchier"})
    generated = versions(client, did)[-1]
    restored = client.post(f"/drafts/{did}/versions/{generated['id']}/restore").json()
    assert restored["content"] == original["content"]
    assert [v["source"] for v in versions(client, did)] == ["restored", "rewrite", "generated"]
    assert versions(client, did)[0]["note"] == "Restored the original version"


def test_unknown_ids(client, run):
    did = draft_id(run, "x")
    assert client.get("/drafts/nope").status_code == 404
    assert client.post(f"/drafts/{did}/versions/nope/restore").status_code == 404


def test_deleting_run_deletes_drafts(client, run):
    did = draft_id(run, "x")
    client.post(f"/drafts/{did}/rewrite", json={"preset": "simpler"})
    assert client.delete(f"/runs/{run['id']}").status_code == 204
    assert client.get(f"/drafts/{did}").status_code == 404
