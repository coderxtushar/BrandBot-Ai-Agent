"""Meta platforms: Threads API and Instagram API with Instagram Login.

Both publish in two steps: create a media container (Meta downloads any image from a public URL),
wait until it's FINISHED, then publish it. Short-lived tokens are swapped for 60-day tokens on
connect and refreshed before they expire.
"""

import asyncio

from backend.publishing.base import (
    Credentials,
    PlatformClient,
    Profile,
    PublishError,
    PublishPayload,
    PublishResult,
    TokenSet,
)


class _MetaClient(PlatformClient):
    graph: str  # e.g. https://graph.threads.net/v1.0
    status_field: str
    poll_interval = 2.0
    poll_timeout = 90.0

    async def _wait_for_container(self, http, container_id: str, token: str) -> None:
        waited = 0.0
        while True:
            body = self.check(
                await http.get(f"{self.graph}/{container_id}", params={"fields": f"{self.status_field},error_message", "access_token": token}),
                "check the upload",
            ).json()
            status = body.get(self.status_field, "")
            if status in ("FINISHED", "PUBLISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                raise PublishError(f"{self.label} rejected the media: {body.get('error_message') or status}")
            if waited >= self.poll_timeout:
                raise PublishError(f"{self.label} is still processing the media; try again shortly.", retryable=True)
            await asyncio.sleep(self.poll_interval)
            waited += self.poll_interval

    async def _permalink(self, http, media_id: str, token: str) -> str | None:
        resp = await http.get(f"{self.graph}/{media_id}", params={"fields": "permalink", "access_token": token})
        return resp.json().get("permalink") if resp.is_success else None


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------


class ThreadsClient(_MetaClient):
    platform = "threads"
    label = "Threads"
    scopes = ["threads_basic", "threads_content_publish", "threads_manage_replies"]
    needs_public_image = True
    graph = "https://graph.threads.net/v1.0"
    status_field = "status"

    def configured(self) -> bool:
        return bool(self.settings.threads_app_id and self.settings.threads_app_secret)

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return self.url(
            "https://threads.net/oauth/authorize",
            client_id=self.settings.threads_app_id,
            redirect_uri=redirect_uri,
            scope=",".join(self.scopes),
            response_type="code",
            state=state,
        )

    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        s = self.settings
        async with self.http() as http:
            short = self.check(
                await http.post(
                    "https://graph.threads.net/oauth/access_token",
                    data={
                        "client_id": s.threads_app_id,
                        "client_secret": s.threads_app_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                ),
                "finish connecting",
            ).json()
            long = self.check(
                await http.get(
                    "https://graph.threads.net/access_token",
                    params={"grant_type": "th_exchange_token", "client_secret": s.threads_app_secret, "access_token": short["access_token"]},
                ),
                "get a long-lived token",
            ).json()
        return TokenSet(long["access_token"], None, long.get("expires_in"), ",".join(self.scopes))

    async def refresh(self, *, access_token: str, refresh_token: str | None) -> TokenSet | None:
        async with self.http() as http:
            body = self.check(
                await http.get(
                    "https://graph.threads.net/refresh_access_token",
                    params={"grant_type": "th_refresh_token", "access_token": access_token},
                ),
                "refresh access",
            ).json()
        return TokenSet(body["access_token"], None, body.get("expires_in"))

    async def fetch_profile(self, access_token: str) -> Profile:
        async with self.http() as http:
            me = self.check(
                await http.get(f"{self.graph}/me", params={"fields": "id,username,name", "access_token": access_token}),
                "read your profile",
            ).json()
        return Profile(external_id=me["id"], display_name=me.get("name") or me.get("username") or "Threads user", username=me.get("username"))

    async def publish(self, creds: Credentials, payload: PublishPayload) -> PublishResult:
        if not payload.parts:
            raise PublishError("Nothing to post.")
        token = creds.access_token
        first_id: str | None = None
        previous: str | None = None
        async with self.http() as http:
            for i, text in enumerate(payload.parts):
                params = {"media_type": "TEXT", "text": text, "access_token": token}
                if i == 0 and payload.image:
                    params |= {"media_type": "IMAGE", "image_url": payload.image.public_url}
                if previous:
                    params["reply_to_id"] = previous
                try:
                    container = self.check(await http.post(f"{self.graph}/me/threads", params=params), f"prepare post {i + 1}").json()["id"]
                    await self._wait_for_container(http, container, token)
                    previous = self.check(
                        await http.post(f"{self.graph}/me/threads_publish", params={"creation_id": container, "access_token": token}),
                        f"publish post {i + 1}",
                    ).json()["id"]
                except PublishError as exc:
                    if first_id:
                        raise PublishError(f"{exc} The first {i} post(s) were published.", retryable=False) from exc
                    raise
                first_id = first_id or previous
            url = await self._permalink(http, first_id, token)
        return PublishResult(external_id=first_id, url=url)


# ---------------------------------------------------------------------------
# Instagram
# ---------------------------------------------------------------------------


class InstagramClient(_MetaClient):
    platform = "instagram"
    label = "Instagram"
    scopes = ["instagram_business_basic", "instagram_business_content_publish"]
    needs_jpeg = True  # Instagram only accepts JPEG images
    needs_public_image = True
    image_required = True  # no text-only posts on Instagram
    graph = "https://graph.instagram.com"
    status_field = "status_code"

    def configured(self) -> bool:
        return bool(self.settings.instagram_app_id and self.settings.instagram_app_secret)

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return self.url(
            "https://www.instagram.com/oauth/authorize",
            client_id=self.settings.instagram_app_id,
            redirect_uri=redirect_uri,
            response_type="code",
            scope=",".join(self.scopes),
            state=state,
        )

    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        s = self.settings
        async with self.http() as http:
            short = self.check(
                await http.post(
                    "https://api.instagram.com/oauth/access_token",
                    data={
                        "client_id": s.instagram_app_id,
                        "client_secret": s.instagram_app_secret,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri,
                        "code": code,
                    },
                ),
                "finish connecting",
            ).json()
            short = short["data"][0] if isinstance(short.get("data"), list) else short  # both shapes are in the wild
            long = self.check(
                await http.get(
                    f"{self.graph}/access_token",
                    params={"grant_type": "ig_exchange_token", "client_secret": s.instagram_app_secret, "access_token": short["access_token"]},
                ),
                "get a long-lived token",
            ).json()
        return TokenSet(long["access_token"], None, long.get("expires_in"), ",".join(self.scopes))

    async def refresh(self, *, access_token: str, refresh_token: str | None) -> TokenSet | None:
        async with self.http() as http:
            body = self.check(
                await http.get(f"{self.graph}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": access_token}),
                "refresh access",
            ).json()
        return TokenSet(body["access_token"], None, body.get("expires_in"))

    async def fetch_profile(self, access_token: str) -> Profile:
        async with self.http() as http:
            me = self.check(
                await http.get(f"{self.graph}/me", params={"fields": "user_id,username,name", "access_token": access_token}),
                "read your profile",
            ).json()
        return Profile(
            external_id=str(me.get("user_id") or me["id"]),
            display_name=me.get("name") or me.get("username") or "Instagram account",
            username=me.get("username"),
        )

    async def publish(self, creds: Credentials, payload: PublishPayload) -> PublishResult:
        if payload.image is None:
            raise PublishError("Instagram posts need an image. Generate one for this draft first.")
        token = creds.access_token
        async with self.http() as http:
            container = self.check(
                await http.post(
                    f"{self.graph}/me/media",
                    params={"image_url": payload.image.public_url, "caption": payload.parts[0] if payload.parts else "", "access_token": token},
                ),
                "prepare the post",
            ).json()["id"]
            await self._wait_for_container(http, container, token)
            media_id = self.check(
                await http.post(f"{self.graph}/me/media_publish", params={"creation_id": container, "access_token": token}),
                "publish the post",
            ).json()["id"]
            url = await self._permalink(http, media_id, token)
        return PublishResult(external_id=media_id, url=url)
