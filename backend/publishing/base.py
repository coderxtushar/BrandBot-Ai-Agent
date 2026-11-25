"""Shared types for platform publishing adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx

from backend.config import Settings
from backend.schemas import Metrics


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None  # seconds
    scope: str = ""


@dataclass(frozen=True)
class Profile:
    external_id: str
    display_name: str
    username: str | None = None


@dataclass(frozen=True)
class Credentials:
    access_token: str
    external_id: str
    username: str | None = None


@dataclass(frozen=True)
class ImageAsset:
    data: bytes
    mime: str
    public_url: str
    alt_text: str = ""


@dataclass(frozen=True)
class PublishPayload:
    parts: list[str]  # one string per post; threads have several
    image: ImageAsset | None = None
    content: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PublishResult:
    external_id: str
    url: str | None = None


class MetricsUnavailable(Exception):
    """The platform doesn't share post stats with this app; the user can type them in."""


class PublishError(Exception):
    """A platform refused or failed a request. `retryable` = worth trying again later (5xx, rate limits, network)."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def _error_detail(body: object) -> str:
    """Pull a human message out of the different error shapes platforms return."""
    if not isinstance(body, dict):
        return str(body)[:300]
    err = body.get("error")
    if isinstance(err, dict):  # Meta: {"error": {"message": ...}}
        return str(err.get("error_user_msg") or err.get("message") or err)[:300]
    for key in ("error_description", "detail", "message", "title"):  # OAuth / X / LinkedIn
        if body.get(key):
            return str(body[key])[:300]
    return str(err or body)[:300]


class PlatformClient(ABC):
    platform: str
    label: str
    scopes: list[str]
    needs_jpeg = False  # convert images to JPEG before publishing
    needs_public_image = False  # the platform fetches the image from a public URL
    supports_image = True
    image_required = False

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._transport = transport

    def http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=httpx.Timeout(30.0, connect=10.0))

    @abstractmethod
    def configured(self) -> bool: ...

    @abstractmethod
    def authorize_url(self, *, state: str, code_challenge: str, redirect_uri: str) -> str: ...

    @abstractmethod
    async def exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> TokenSet: ...

    @abstractmethod
    async def fetch_profile(self, access_token: str) -> Profile: ...

    async def refresh(self, *, access_token: str, refresh_token: str | None) -> TokenSet | None:
        """Return fresh tokens, or None if this platform can't refresh."""
        return None

    @abstractmethod
    async def publish(self, creds: Credentials, payload: PublishPayload) -> PublishResult: ...

    async def fetch_metrics(self, creds: Credentials, external_id: str) -> "Metrics":
        raise MetricsUnavailable(f"{self.label} doesn't share post stats with this app. Add the numbers yourself.")

    # -- helpers --------------------------------------------------------------

    def check(self, resp: httpx.Response, action: str) -> httpx.Response:
        if resp.is_success:
            return resp
        try:
            detail = _error_detail(resp.json())
        except ValueError:  # not JSON
            detail = resp.text[:300]
        retryable = resp.status_code == 429 or resp.status_code >= 500
        raise PublishError(f"{self.label} couldn't {action} ({resp.status_code}): {detail or 'no details'}", retryable)

    @staticmethod
    def url(base: str, **params: str) -> str:
        return f"{base}?{urlencode(params)}"
