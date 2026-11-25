"""Where generated media lives. Local disk for now; swap for S3/GCS by implementing the same methods."""

import logging
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg"}


class LocalMediaStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def save(self, data: bytes, mime: str, folder: str = "images") -> str:
        """Store bytes and return a storage key like 'images/<uuid>.png'."""
        ext = EXTENSIONS.get(mime, "bin")
        key = f"{folder}/{uuid.uuid4().hex}.{ext}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def path(self, key: str) -> Path | None:
        """Absolute path for a key, or None if it escapes the media root or doesn't exist."""
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            return None
        return path

    def delete(self, key: str) -> None:
        path = self.path(key)
        if path is not None:
            try:
                path.unlink()
            except OSError:
                log.warning("Could not delete media file %s", key, exc_info=True)
