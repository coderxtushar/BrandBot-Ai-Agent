"""X: OAuth 2.0 Authorization Code with PKCE, and threads via POST /2/tweets replies.

Images are not attached on X: X's own documentation currently contradicts itself on uploading media
with OAuth 2.0 user tokens, so threads are published as text.
"""

import base64

from backend.publishing.base import (
    Credentials,
    PlatformClient,
    Profile,
    PublishError,
    PublishPayload,
    PublishResult,
    TokenSet,
)

AUTH_URL = "https://x.com/i/oauth2/authorize"
API = "https://api.x.com"


class XClient(PlatformClient):
    platform = "x"
    label = "X"
    scopes = ["tweet.read", "tweet.write", "users.read", "offline.access"]
    supports_image = False

    def configured(self) -> bool:
        return bool(self.settings.x_client_id and self.settings.x_client_secret)

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return self.url(
            AUTH_URL,
            response_type="code",
            client_id=self.settings.x_client_id,
            redirect_uri=redirect_uri,
            scope=" ".join(self.scopes),
            state=state,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )

    def _basic(self) -> dict:
        raw = f"{self.settings.x_client_id}:{self.settings.x_client_secret}".encode()
        return {"Authorization": f"Basic {base64.b64encode(raw).decode()}"}

    async def _token(self, data: dict, action: str) -> TokenSet:
        async with self.http() as http:
            body = self.check(
                await http.post(f"{API}/2/oauth2/token", data=data | {"client_id": self.settings.x_client_id}, headers=self._basic()),
                action,
            ).json()
        return TokenSet(body["access_token"], body.get("refresh_token"), body.get("expires_in"), body.get("scope", ""))

    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        return await self._token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri, "code_verifier": code_verifier},
            "finish connecting",
        )

    async def refresh(self, *, access_token: str, refresh_token: str | None) -> TokenSet | None:
        if not refresh_token:
            return None
        return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token}, "refresh access")

    async def fetch_profile(self, access_token: str) -> Profile:
        async with self.http() as http:
            data = self.check(
                await http.get(f"{API}/2/users/me", headers={"Authorization": f"Bearer {access_token}"}),
                "read your profile",
            ).json()["data"]
        return Profile(external_id=data["id"], display_name=data.get("name") or data["username"], username=data.get("username"))

    async def publish(self, creds: Credentials, payload: PublishPayload) -> PublishResult:
        if not payload.parts:
            raise PublishError("Nothing to post.")
        headers = {"Authorization": f"Bearer {creds.access_token}"}
        first_id: str | None = None
        previous: str | None = None
        async with self.http() as http:
            for i, text in enumerate(payload.parts):
                body: dict = {"text": text}
                if previous:
                    body["reply"] = {"in_reply_to_tweet_id": previous}
                try:
                    resp = self.check(await http.post(f"{API}/2/tweets", json=body, headers=headers), f"post tweet {i + 1}")
                except PublishError as exc:
                    if first_id:  # part of the thread is live: say so instead of retrying (which would duplicate it)
                        raise PublishError(f"{exc} The first {i} tweet(s) were published.", retryable=False) from exc
                    raise
                previous = resp.json()["data"]["id"]
                first_id = first_id or previous
        handle = creds.username or "i"
        return PublishResult(external_id=first_id, url=f"https://x.com/{handle}/status/{first_id}")
