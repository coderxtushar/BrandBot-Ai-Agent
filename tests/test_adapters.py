"""The real platform adapters, against a mocked network. Checks the requests match each platform's API."""

import base64
import io
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from backend.config import Settings
from backend.publishing.base import Credentials, ImageAsset, PublishError, PublishPayload
from backend.publishing.linkedin import LinkedInClient, to_little_text
from backend.publishing.meta import InstagramClient, ThreadsClient
from backend.publishing.service import _to_jpeg
from backend.publishing.x import XClient

SETTINGS = Settings(
    linkedin_client_id="li-id", linkedin_client_secret="li-secret", linkedin_api_version="202607",
    x_client_id="x-id", x_client_secret="x-secret",
    threads_app_id="th-id", threads_app_secret="th-secret",
    instagram_app_id="ig-id", instagram_app_secret="ig-secret",
)
IMAGE = ImageAsset(data=b"\xff\xd8jpeg", mime="image/jpeg", public_url="https://api.example.com/media/images/a.jpg", alt_text="A desk")


class Recorder:
    """A fake network: routes requests to handlers and records them."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        for (method, match), handler in self.routes.items():
            if request.method == method and match in str(request.url):
                return handler(request)
        return httpx.Response(404, json={"message": f"unexpected {request.method} {request.url}"})

    def transport(self):
        return httpx.MockTransport(self)


def form(req: httpx.Request) -> dict:
    return {k: v[0] for k, v in parse_qs(req.content.decode()).items()}


def query(req: httpx.Request) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(str(req.url)).query).items()}


# --- LinkedIn -------------------------------------------------------------------


def test_little_text_escaping():
    assert to_little_text("Ship it (today) #MLOps #data_science!") == "Ship it \\(today\\) {hashtag|\\#|MLOps} {hashtag|\\#|data\\_science}!"
    assert to_little_text("a*b_c [x] {y} <z> @me ~ |") == "a\\*b\\_c \\[x\\] \\{y\\} \\<z\\> \\@me \\~ \\|"


async def test_linkedin_publish_with_image():
    net = Recorder({
        ("POST", "/rest/images"): lambda r: httpx.Response(200, json={"value": {"uploadUrl": "https://upload.linkedin.test/abc", "image": "urn:li:image:42"}}),
        ("PUT", "upload.linkedin.test"): lambda r: httpx.Response(201),
        ("POST", "/rest/posts"): lambda r: httpx.Response(201, headers={"x-restli-id": "urn:li:share:7"}),
    })
    client = LinkedInClient(SETTINGS, net.transport())
    result = await client.publish(Credentials("tok", "person-1"), PublishPayload(parts=["Hello (world) #AI"], image=IMAGE))

    init, put, post = net.calls
    assert query(init)["action"] == "initializeUpload"
    assert json.loads(init.content) == {"initializeUploadRequest": {"owner": "urn:li:person:person-1"}}
    assert put.content == IMAGE.data and put.headers["Authorization"] == "Bearer tok"
    body = json.loads(post.content)
    assert post.headers["LinkedIn-Version"] == "202607" and post.headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert body["author"] == "urn:li:person:person-1" and body["visibility"] == "PUBLIC"
    assert body["commentary"] == "Hello \\(world\\) {hashtag|\\#|AI}"
    assert body["content"] == {"media": {"id": "urn:li:image:42", "altText": "A desk"}}
    assert result.url == "https://www.linkedin.com/feed/update/urn:li:share:7/"


async def test_linkedin_connect_and_profile():
    net = Recorder({
        ("POST", "oauth/v2/accessToken"): lambda r: httpx.Response(200, json={"access_token": "A", "expires_in": 5184000, "scope": "openid,profile,w_member_social"}),
        ("GET", "/v2/userinfo"): lambda r: httpx.Response(200, json={"sub": "abc123", "name": "Ada L"}),
    })
    client = LinkedInClient(SETTINGS, net.transport())
    url = client.authorize_url(state="S", code_challenge="C", redirect_uri="https://api.example.com/cb")
    q = query(httpx.Request("GET", url))
    assert q["scope"] == "openid profile w_member_social" and q["state"] == "S" and q["client_id"] == "li-id"
    tokens = await client.exchange_code(code="CODE", code_verifier="", redirect_uri="https://api.example.com/cb")
    assert tokens.access_token == "A" and tokens.expires_in == 5184000
    f = form(net.calls[0])
    assert f["grant_type"] == "authorization_code" and f["client_secret"] == "li-secret" and f["redirect_uri"] == "https://api.example.com/cb"
    profile = await client.fetch_profile("A")
    assert profile.external_id == "abc123" and profile.display_name == "Ada L"
    assert await client.refresh(access_token="A", refresh_token=None) is None


# --- X --------------------------------------------------------------------------


async def test_x_publishes_thread_as_replies():
    ids = iter(["100", "101", "102"])
    net = Recorder({("POST", "/2/tweets"): lambda r: httpx.Response(201, json={"data": {"id": next(ids), "text": "…"}})})
    client = XClient(SETTINGS, net.transport())
    result = await client.publish(Credentials("tok", "u1", "ada"), PublishPayload(parts=["one", "2/3 two", "3/3 three"]))
    bodies = [json.loads(c.content) for c in net.calls]
    assert bodies == [
        {"text": "one"},
        {"text": "2/3 two", "reply": {"in_reply_to_tweet_id": "100"}},
        {"text": "3/3 three", "reply": {"in_reply_to_tweet_id": "101"}},
    ]
    assert result.url == "https://x.com/ada/status/100"


async def test_x_partial_thread_failure_is_not_retried():
    responses = iter([httpx.Response(201, json={"data": {"id": "100"}}), httpx.Response(503, json={"title": "Service Unavailable"})])
    net = Recorder({("POST", "/2/tweets"): lambda r: next(responses)})
    with pytest.raises(PublishError) as err:
        await XClient(SETTINGS, net.transport()).publish(Credentials("tok", "u1"), PublishPayload(parts=["a", "b"]))
    assert not err.value.retryable and "first 1 tweet" in str(err.value)


async def test_x_oauth_uses_pkce_and_basic_auth():
    net = Recorder({
        ("POST", "/2/oauth2/token"): lambda r: httpx.Response(200, json={"access_token": "A", "refresh_token": "R", "expires_in": 7200}),
        ("GET", "/2/users/me"): lambda r: httpx.Response(200, json={"data": {"id": "9", "name": "Ada", "username": "ada"}}),
    })
    client = XClient(SETTINGS, net.transport())
    q = query(httpx.Request("GET", client.authorize_url(state="S", code_challenge="CH", redirect_uri="https://cb")))
    assert q["code_challenge"] == "CH" and q["code_challenge_method"] == "S256" and "offline.access" in q["scope"]
    tokens = await client.exchange_code(code="C", code_verifier="V", redirect_uri="https://cb")
    req = net.calls[0]
    assert form(req)["code_verifier"] == "V"
    assert req.headers["Authorization"] == "Basic " + base64.b64encode(b"x-id:x-secret").decode()
    assert tokens.refresh_token == "R"
    assert (await client.fetch_profile("A")).username == "ada"


def test_error_classification():
    client = XClient(SETTINGS)
    with pytest.raises(PublishError) as rate:
        client.check(httpx.Response(429, json={"title": "Too Many Requests"}), "post")
    assert rate.value.retryable
    with pytest.raises(PublishError) as bad:
        client.check(httpx.Response(403, json={"detail": "You are not permitted"}), "post")
    assert not bad.value.retryable and "You are not permitted" in str(bad.value)


# --- Threads ----------------------------------------------------------------------


async def test_threads_container_wait_publish_and_reply_chain():
    containers = iter(["c1", "c2"])
    published = iter(["m1", "m2"])
    statuses = iter(["IN_PROGRESS", "FINISHED", "FINISHED"])
    net = Recorder({
        ("POST", "/me/threads_publish"): lambda r: httpx.Response(200, json={"id": next(published)}),
        ("POST", "/me/threads"): lambda r: httpx.Response(200, json={"id": next(containers)}),
        ("GET", "fields=permalink"): lambda r: httpx.Response(200, json={"permalink": "https://www.threads.net/@ada/post/xyz"}),
        ("GET", "/v1.0/c"): lambda r: httpx.Response(200, json={"status": next(statuses)}),
    })
    client = ThreadsClient(SETTINGS, net.transport())
    client.poll_interval = 0
    result = await client.publish(Credentials("tok", "u1"), PublishPayload(parts=["first", "second"], image=IMAGE))

    creates = [query(c) for c in net.calls if c.method == "POST" and c.url.path.endswith("/me/threads")]
    assert creates[0]["media_type"] == "IMAGE" and creates[0]["image_url"] == IMAGE.public_url and "reply_to_id" not in creates[0]
    assert creates[1]["media_type"] == "TEXT" and creates[1]["reply_to_id"] == "m1"
    publishes = [query(c)["creation_id"] for c in net.calls if c.url.path.endswith("threads_publish")]
    assert publishes == ["c1", "c2"]
    assert result.external_id == "m1" and result.url.endswith("/post/xyz")


async def test_threads_rejected_media_is_reported():
    net = Recorder({
        ("POST", "/me/threads"): lambda r: httpx.Response(200, json={"id": "c1"}),
        ("GET", "/v1.0/c1"): lambda r: httpx.Response(200, json={"status": "ERROR", "error_message": "Image too small"}),
    })
    client = ThreadsClient(SETTINGS, net.transport())
    client.poll_interval = 0
    with pytest.raises(PublishError, match="Image too small"):
        await client.publish(Credentials("tok", "u1"), PublishPayload(parts=["x"], image=IMAGE))


async def test_threads_connect_swaps_for_long_lived_token():
    net = Recorder({
        ("POST", "oauth/access_token"): lambda r: httpx.Response(200, json={"access_token": "SHORT", "user_id": 5}),
        ("GET", "/access_token"): lambda r: httpx.Response(200, json={"access_token": "LONG", "token_type": "bearer", "expires_in": 5183944}),
    })
    tokens = await ThreadsClient(SETTINGS, net.transport()).exchange_code(code="C", code_verifier="", redirect_uri="https://cb")
    assert tokens.access_token == "LONG" and tokens.expires_in == 5183944
    q = query(net.calls[1])
    assert q["grant_type"] == "th_exchange_token" and q["access_token"] == "SHORT" and q["client_secret"] == "th-secret"


# --- Instagram --------------------------------------------------------------------


async def test_instagram_publishes_image_with_caption():
    net = Recorder({
        ("POST", "/me/media_publish"): lambda r: httpx.Response(200, json={"id": "M1"}),
        ("POST", "/me/media"): lambda r: httpx.Response(200, json={"id": "C1"}),
        ("GET", "fields=permalink"): lambda r: httpx.Response(200, json={"permalink": "https://www.instagram.com/p/abc/"}),
        ("GET", "/C1"): lambda r: httpx.Response(200, json={"status_code": "FINISHED"}),
    })
    client = InstagramClient(SETTINGS, net.transport())
    client.poll_interval = 0
    result = await client.publish(Credentials("tok", "17841"), PublishPayload(parts=["Caption #ml"], image=IMAGE))
    create = query(net.calls[0])
    assert create["image_url"] == IMAGE.public_url and create["caption"] == "Caption #ml"
    assert query(net.calls[2])["creation_id"] == "C1"
    assert result.url == "https://www.instagram.com/p/abc/"


async def test_instagram_refuses_text_only():
    with pytest.raises(PublishError, match="need an image"):
        await InstagramClient(SETTINGS).publish(Credentials("tok", "1"), PublishPayload(parts=["hi"]))


async def test_instagram_token_shapes():
    net = Recorder({
        ("POST", "api.instagram.com/oauth/access_token"): lambda r: httpx.Response(200, json={"data": [{"access_token": "SHORT", "user_id": "1"}]}),
        ("GET", "graph.instagram.com/access_token"): lambda r: httpx.Response(200, json={"access_token": "LONG", "expires_in": 5184000}),
        ("GET", "/me"): lambda r: httpx.Response(200, json={"id": "app-scoped", "user_id": "17841", "username": "ada.codes"}),
    })
    client = InstagramClient(SETTINGS, net.transport())
    tokens = await client.exchange_code(code="C", code_verifier="", redirect_uri="https://cb")
    assert tokens.access_token == "LONG"
    profile = await client.fetch_profile("LONG")
    assert profile.external_id == "17841" and profile.username == "ada.codes"


# --- images -------------------------------------------------------------------------


def test_png_is_converted_to_jpeg_for_instagram():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (40, 50), (255, 72, 176, 128)).save(buf, "PNG")
    jpeg = _to_jpeg(buf.getvalue())
    assert jpeg[:3] == b"\xff\xd8\xff"
    with Image.open(io.BytesIO(jpeg)) as img:
        assert img.format == "JPEG" and img.size == (40, 50)
