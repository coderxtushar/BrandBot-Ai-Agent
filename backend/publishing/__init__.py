"""Connecting social accounts and publishing drafts to them."""

from backend.config import Settings
from backend.publishing.base import PlatformClient, PublishError
from backend.publishing.linkedin import LinkedInClient
from backend.publishing.meta import InstagramClient, ThreadsClient
from backend.publishing.x import XClient

CLIENTS = {"linkedin": LinkedInClient, "x": XClient, "threads": ThreadsClient, "instagram": InstagramClient}


def build_clients(settings: Settings) -> dict[str, PlatformClient]:
    """Real platform clients, or fakes in DEMO_MODE."""
    if settings.demo_mode:
        from backend.publishing.fake import FakePlatformClient

        return {p: FakePlatformClient(settings, p) for p in CLIENTS}
    return {p: cls(settings) for p, cls in CLIENTS.items()}


__all__ = ["CLIENTS", "PlatformClient", "PublishError", "build_clients"]
