"""Offline stand-in for every platform (tests and DEMO_MODE).

"Connecting" skips the platform and sends the browser straight back to our callback with a demo code,
so the full state-checking OAuth round-trip still runs.
"""

import itertools

from backend.publishing.base import (
    Credentials,
    PlatformClient,
    Profile,
    PublishError,
    PublishPayload,
    PublishResult,
    TokenSet,
)

LABELS = {"linkedin": "LinkedIn", "x": "X", "threads": "Threads", "instagram": "Instagram"}
_ids = itertools.count(1000)


class FakePlatformClient(PlatformClient):
    def __init__(self, settings, platform: str):
        super().__init__(settings)
        self.platform = platform
        self.label = LABELS[platform]
        self.scopes = ["demo"]
        self.image_required = platform == "instagram"
        self.supports_image = platform != "x"
        self.posts: list[tuple[Credentials, PublishPayload]] = []
        self.fail_next: PublishError | None = None
        self.refreshed = 0

    def configured(self) -> bool:
        return True

    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str:
        return self.url(redirect_uri, code="demo-code", state=state)

    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet:
        if code != "demo-code":
            raise PublishError("Invalid authorization code.")
        return TokenSet(f"demo-access-{self.platform}", f"demo-refresh-{self.platform}", 3600)

    async def refresh(self, *, access_token: str, refresh_token: str | None) -> TokenSet | None:
        self.refreshed += 1
        return TokenSet(f"demo-access-{self.platform}-r{self.refreshed}", refresh_token, 3600)

    async def fetch_profile(self, access_token: str) -> Profile:
        return Profile(external_id=f"demo-{self.platform}", display_name=f"Demo {self.label} account", username=f"demo_{self.platform}")

    async def publish(self, creds: Credentials, payload: PublishPayload) -> PublishResult:
        if self.fail_next:
            err, self.fail_next = self.fail_next, None
            raise err
        if self.image_required and payload.image is None:
            raise PublishError("Instagram posts need an image. Generate one for this draft first.")
        self.posts.append((creds, payload))
        post_id = str(next(_ids))
        return PublishResult(external_id=post_id, url=f"https://example.com/demo/{self.platform}/{post_id}")
