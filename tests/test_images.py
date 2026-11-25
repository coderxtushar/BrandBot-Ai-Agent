"""Step 7: AI visuals for drafts."""

from types import SimpleNamespace

import pytest

from backend.config import Settings
from backend.services.images import GeminiImageGenerator
from tests.conftest import stream
from tests.test_brands import make_brand

PLATFORMS = ["linkedin", "x", "threads", "instagram", "medium", "youtube_shorts"]


@pytest.fixture
def run(client):
    b = make_brand(client)
    return stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": PLATFORMS})[-1][1]


def draft_id(run, platform):
    return next(r for r in run["results"] if r["platform"] == platform)["drafts"][0]["id"]


def test_generate_image_for_each_platform_aspect(client, run, image_gen):
    expected = {"linkedin": "1:1", "x": "16:9", "threads": "4:5", "instagram": "4:5", "medium": "16:9", "youtube_shorts": "9:16"}
    for platform, aspect in expected.items():
        res = client.post(f"/drafts/{draft_id(run, platform)}/images", json={})
        assert res.status_code == 201, res.text
        img = res.json()
        assert img["aspect_ratio"] == aspect and img["url"].startswith("/media/images/")
        assert img["alt_text"] and img["prompt"]
    assert [a for _, a in image_gen.prompts] == list(expected.values())


def test_image_is_served_and_listed_in_run(client, run, storage):
    did = draft_id(run, "linkedin")
    img = client.post(f"/drafts/{did}/images", json={"style": "illustration"}).json()
    media = client.get(img["url"])
    assert media.status_code == 200 and media.headers["content-type"].startswith("image/svg+xml")
    assert "default-src 'none'" in media.headers["content-security-policy"]
    assert img["style"] == "illustration"

    saved = client.get(f"/runs/{run['id']}").json()
    linkedin = next(r for r in saved["results"] if r["platform"] == "linkedin")
    assert [i["id"] for i in linkedin["drafts"][0]["images"]] == [img["id"]]
    assert [i["id"] for i in client.get(f"/drafts/{did}/images").json()] == [img["id"]]


def test_art_director_prompt_uses_brand_style_idea_and_writer_suggestion(client, run, llm):
    client.post(f"/drafts/{draft_id(run, 'instagram')}/images", json={"idea": "a lighthouse at dawn", "style": "3d"})
    name, system, user = llm.prompts[-1]
    assert name == "ImagePrompt"
    assert "a lighthouse at dawn" in user and "soft 3D render" in user
    assert "navy and warm amber" in user  # brand visual_style
    assert "Minimal desk with laptop" in user  # the Instagram writer's image_prompt
    assert "NEVER include text" in system


def test_delete_image_removes_file(client, run, storage):
    img = client.post(f"/drafts/{draft_id(run, 'x')}/images", json={}).json()
    key = img["url"].removeprefix("/media/")
    assert storage.path(key) is not None
    assert client.delete(f"/images/{img['id']}").status_code == 204
    assert storage.path(key) is None
    assert client.get(img["url"]).status_code == 404
    assert client.delete(f"/images/{img['id']}").status_code == 404


def test_deleting_run_or_brand_removes_files(client, run, storage):
    a = client.post(f"/drafts/{draft_id(run, 'x')}/images", json={}).json()["url"].removeprefix("/media/")
    client.delete(f"/runs/{run['id']}")
    assert storage.path(a) is None

    b = make_brand(client, "Second")
    run2 = stream(client, f"/brands/{b['id']}/runs/stream", {"platforms": ["medium"]})[-1][1]
    key = client.post(f"/drafts/{draft_id(run2, 'medium')}/images", json={}).json()["url"].removeprefix("/media/")
    client.delete(f"/brands/{b['id']}")
    assert storage.path(key) is None


def test_generation_failure_is_502_and_saves_nothing(client, run, image_gen, storage):
    image_gen.fail = True
    did = draft_id(run, "x")
    res = client.post(f"/drafts/{did}/images", json={})
    assert res.status_code == 502 and "image model unavailable" in res.json()["detail"]
    assert client.get(f"/drafts/{did}/images").json() == []


def test_media_paths_cannot_escape(client):
    assert client.get("/media/../tests/conftest.py").status_code == 404
    assert client.get("/media/%2e%2e/%2e%2e/etc/passwd").status_code == 404


# --- the real Gemini adapter, with the network call mocked --------------------------------


def _response(parts, block_reason=None):
    content = SimpleNamespace(parts=parts)
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=content)],
        prompt_feedback=SimpleNamespace(block_reason=block_reason) if block_reason else None,
    )


async def test_gemini_adapter_extracts_inline_image(monkeypatch):
    gen = GeminiImageGenerator(Settings(google_api_key="test", gemini_image_model="img-model"))
    captured = {}

    async def fake_generate(model, contents, config):
        captured.update(model=model, contents=contents, aspect=config.image_config.aspect_ratio)
        text_part = SimpleNamespace(inline_data=None, text="here you go")
        image_part = SimpleNamespace(inline_data=SimpleNamespace(data=b"\x89PNG...", mime_type="image/png"))
        return _response([text_part, image_part])

    monkeypatch.setattr(gen._client.aio.models, "generate_content", fake_generate)
    out = await gen.generate("a lighthouse", "4:5")
    assert out.data == b"\x89PNG..." and out.mime == "image/png" and out.model == "img-model"
    assert captured == {"model": "img-model", "contents": "a lighthouse", "aspect": "4:5"}


async def test_gemini_adapter_reports_blocked_prompt(monkeypatch):
    gen = GeminiImageGenerator(Settings(google_api_key="test"))

    async def fake_generate(**_):
        return _response([], block_reason="SAFETY")

    monkeypatch.setattr(gen._client.aio.models, "generate_content", fake_generate)
    with pytest.raises(RuntimeError, match="SAFETY"):
        await gen.generate("x", "1:1")


@pytest.mark.parametrize(
    "error, says",
    [
        ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_free_tier_requests, limit: 0", "free tier"),
        ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generate_content_requests, limit: 10", "Try again in a minute"),
    ],
)
def test_quota_errors_say_what_to_do(client, run, image_gen, error, says):
    image_gen.fail = RuntimeError(error)
    res = client.post(f"/drafts/{draft_id(run, 'x')}/images", json={})
    assert res.status_code == 502 and says in res.json()["detail"] and "RESOURCE_EXHAUSTED" not in res.json()["detail"]
