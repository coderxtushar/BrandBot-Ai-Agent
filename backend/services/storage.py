"""Where generated media lives: local disk (development, a Docker volume) or Google Cloud Storage (Cloud Run).

Both backends speak the same async interface: save(bytes) -> key, read(key) -> bytes | None, delete(key).
Keys look like 'images/<32 hex>.png'. The API serves them at /media/<key>, so the bucket can stay private.
"""

import asyncio
import logging
import re
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg"}
MIME_TYPES = {ext: mime for mime, ext in EXTENSIONS.items()}
_KEY = re.compile(r"^[a-z]+/[0-9a-f]{32}\.[a-z]+$")


def new_key(mime: str, folder: str = "images") -> str:
    return f"{folder}/{uuid.uuid4().hex}.{EXTENSIONS.get(mime, 'bin')}"


def valid_key(key: str) -> bool:
    """Only keys we generated: no path tricks, nothing outside our folders."""
    return bool(_KEY.match(key))


def mime_for(key: str) -> str:
    return MIME_TYPES.get(key.rsplit(".", 1)[-1], "application/octet-stream")


class LocalMediaStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def path(self, key: str) -> Path | None:
        """Absolute path for a key, or None if it escapes the media root or doesn't exist."""
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            return None
        return path

    async def save(self, data: bytes, mime: str, folder: str = "images") -> str:
        key = new_key(mime, folder)
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    async def read(self, key: str) -> bytes | None:
        path = self.path(key) if valid_key(key) else None
        return path.read_bytes() if path else None

    async def delete(self, key: str) -> None:
        path = self.path(key)
        if path is not None:
            try:
                path.unlink()
            except OSError:
                log.warning("Could not delete media file %s", key, exc_info=True)


class GcsMediaStorage:
    """A Google Cloud Storage bucket. On Cloud Run the service account's credentials are picked up automatically;
    it needs roles/storage.objectUser on the bucket. The client library is blocking, so calls run in a thread."""

    def __init__(self, bucket_name: str, bucket=None):
        if bucket is None:
            from google.cloud import storage

            bucket = storage.Client().bucket(bucket_name)
        self.bucket = bucket

    async def save(self, data: bytes, mime: str, folder: str = "images") -> str:
        key = new_key(mime, folder)
        blob = self.bucket.blob(key)
        blob.cache_control = "public, max-age=31536000, immutable"  # keys are random and never reused
        await asyncio.to_thread(blob.upload_from_string, data, content_type=mime)
        return key

    async def read(self, key: str) -> bytes | None:
        if not valid_key(key):
            return None
        from google.api_core.exceptions import NotFound

        try:
            return await asyncio.to_thread(self.bucket.blob(key).download_as_bytes)
        except NotFound:
            return None

    async def delete(self, key: str) -> None:
        if not valid_key(key):
            return
        from google.api_core.exceptions import NotFound

        try:
            await asyncio.to_thread(self.bucket.blob(key).delete)
        except NotFound:
            pass
        except Exception:  # best effort: a leftover object costs fractions of a cent
            log.warning("Could not delete media object %s", key, exc_info=True)


def build_storage(settings) -> LocalMediaStorage | GcsMediaStorage:
    if settings.media_backend == "gcs":
        if not settings.gcs_bucket:
            raise RuntimeError("MEDIA_BACKEND=gcs needs GCS_BUCKET.")
        return GcsMediaStorage(settings.gcs_bucket)
    return LocalMediaStorage(settings.media_dir)
