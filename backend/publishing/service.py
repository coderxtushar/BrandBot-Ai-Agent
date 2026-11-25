"""Publishing one post, and the scheduler that publishes due posts."""

import asyncio
import io
import logging
from datetime import timedelta

from backend.config import Settings
from backend.db import accounts as acc
from backend.db.models import Publication, utcnow
from backend.db.session import Database
from backend.platforms import get_spec
from backend.publishing.base import Credentials, ImageAsset, PlatformClient, PublishError, PublishPayload
from backend.security import TokenCipher

log = logging.getLogger("brandbot.publishing")

MAX_ATTEMPTS = 3
REFRESH_WINDOW = timedelta(days=1)  # refresh tokens that expire within a day
STUCK_AFTER = timedelta(minutes=15)


def _is_local(url: str) -> bool:
    return any(h in url for h in ("://localhost", "://127.0.0.1", "://0.0.0.0", "://[::1]"))


def _to_jpeg(data: bytes) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as img:
        out = io.BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
        return out.getvalue()


class Publisher:
    def __init__(self, db: Database, clients: dict[str, PlatformClient], storage, cipher: TokenCipher, settings: Settings):
        self.db, self.clients, self.storage, self.cipher, self.settings = db, clients, storage, cipher, settings

    async def _credentials(self, s, pub: Publication, client: PlatformClient) -> Credentials:
        account = pub.account
        if account is None:
            raise PublishError("The account was disconnected. Connect it again and reschedule.")
        token = self.cipher.decrypt(account.access_token)
        if account.expires_at and account.expires_at - utcnow() < REFRESH_WINDOW:
            refresh = self.cipher.decrypt(account.refresh_token) if account.refresh_token else None
            fresh = await client.refresh(access_token=token, refresh_token=refresh)
            if fresh is None:
                if account.expires_at <= utcnow():
                    raise PublishError(f"Your {client.label} connection expired. Reconnect it in Connections.")
            else:
                token = fresh.access_token
                account.access_token = self.cipher.encrypt(fresh.access_token)
                if fresh.refresh_token:
                    account.refresh_token = self.cipher.encrypt(fresh.refresh_token)
                account.expires_at = utcnow() + timedelta(seconds=fresh.expires_in) if fresh.expires_in else None
                await s.commit()
        return Credentials(access_token=token, external_id=account.external_id, username=account.username)

    def _image(self, pub: Publication, client: PlatformClient) -> ImageAsset | None:
        draft = pub.draft
        if not (pub.include_image and client.supports_image and draft.images):
            return None
        img = next((i for i in draft.images if i.id == pub.image_id), draft.images[0])
        path = self.storage.path(img.storage_key)
        if path is None:
            raise PublishError("The image file is missing. Generate a new image or publish without it.")
        data, mime, key = path.read_bytes(), img.mime, img.storage_key
        if client.needs_jpeg and mime != "image/jpeg":
            try:
                data, mime = _to_jpeg(data), "image/jpeg"
            except Exception as exc:  # e.g. demo SVGs
                raise PublishError(f"This image can't be converted to JPEG for {client.label}: {exc}") from exc
            key = pub.asset_key or self.storage.save(data, mime)
            pub.asset_key = key
        public_url = f"{self.settings.api_public_url.rstrip('/')}/media/{key}"
        if client.needs_public_image and _is_local(public_url) and not self.settings.demo_mode:
            raise PublishError(
                f"{client.label} downloads images from a public address, but API_PUBLIC_URL is {self.settings.api_public_url}. "
                "Set it to a public https URL (a tunnel works for testing), or publish without the image."
            )
        return ImageAsset(data=data, mime=mime, public_url=public_url, alt_text=img.alt_text)

    async def publish(self, pub_id: str) -> None:
        """Publish a post that was already claimed (status 'publishing'), and record the outcome."""
        async with self.db.sessions() as s:
            pub = await acc.get_publication(s, pub_id)
            if pub is None or pub.status != "publishing":
                return
            client = self.clients.get(pub.platform)
            try:
                if client is None:
                    raise PublishError(f"Publishing to {pub.platform} isn't supported.")
                creds = await self._credentials(s, pub, client)
                spec = get_spec(pub.platform)
                image = self._image(pub, client)
                if client.image_required and image is None:
                    raise PublishError(f"{client.label} posts need an image. Generate one for this draft first.")
                content = spec.content_model.model_validate(pub.draft.content)
                payload = PublishPayload(parts=spec.post_parts(content), image=image, content=pub.draft.content)
                result = await client.publish(creds, payload)
            except Exception as exc:
                retryable = exc.retryable if isinstance(exc, PublishError) else True
                message = str(exc) if isinstance(exc, PublishError) else f"Unexpected error: {exc}"
                if retryable and pub.attempts < MAX_ATTEMPTS:
                    pub.status = "scheduled"
                    pub.scheduled_at = utcnow() + timedelta(minutes=5 * pub.attempts)
                    pub.error = f"{message} Retrying automatically."
                else:
                    pub.status = "failed"
                    pub.error = message
                log.warning("Publication %s (%s) failed: %s", pub.id, pub.platform, message)
            else:
                pub.status = "published"
                pub.published_at = utcnow()
                pub.external_id = result.external_id
                pub.external_url = result.url
                pub.error = None
                log.info("Published %s to %s: %s", pub.id, pub.platform, result.url)
            await s.commit()

    async def publish_now(self, pub_id: str) -> None:
        async with self.db.sessions() as s:
            claimed = await acc.claim(s, pub_id)
        if claimed:
            await self.publish(pub_id)

    async def run_due(self) -> int:
        """Publish everything that's due. Safe to run from several processes at once."""
        async with self.db.sessions() as s:
            await acc.fail_stuck(s, utcnow() - STUCK_AFTER)
            ids = await acc.due_ids(s, utcnow())
        done = 0
        for pub_id in ids:
            async with self.db.sessions() as s:
                if not await acc.claim(s, pub_id):
                    continue  # another worker took it
            await self.publish(pub_id)
            done += 1
        return done


class Scheduler:
    """Background loop inside the API process. For several API replicas, the atomic claim prevents duplicates."""

    def __init__(self, publisher: Publisher, interval: float):
        self.publisher, self.interval = publisher, interval
        self._task: asyncio.Task | None = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.publisher.run_due()
            except Exception:
                log.exception("Scheduler tick failed")
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="brandbot-scheduler")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
