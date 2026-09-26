"""
Storage abstraction layer.

Currently wraps the local filesystem. In future, replace get_storage()
with an S3/GCS implementation without changing callers.
"""
from pathlib import Path
from typing import Protocol
import os


class StorageBackend(Protocol):
    """Minimal interface that any storage backend must satisfy."""

    def save(self, data: bytes, relative_path: str) -> str:
        """Persist bytes to relative_path. Returns the stored path/key."""
        ...

    def load(self, path: str) -> bytes:
        """Load bytes from path/key."""
        ...

    def delete(self, path: str) -> None:
        """Delete a stored object."""
        ...

    def exists(self, path: str) -> bool:
        """Return True if the path/key exists."""
        ...

    def size(self, path: str) -> int:
        """Return file size in bytes."""
        ...


class LocalStorage:
    """Local filesystem storage backend."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        base_dir.mkdir(parents=True, exist_ok=True)

    def full_path(self, relative_or_absolute: str) -> Path:
        p = Path(relative_or_absolute)
        if p.is_absolute():
            return p
        return self.base_dir / p

    def save(self, data: bytes, relative_path: str) -> str:
        dest = self.full_path(relative_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def load(self, path: str) -> bytes:
        return self.full_path(path).read_bytes()

    def delete(self, path: str) -> None:
        self.full_path(path).unlink(missing_ok=True)

    def exists(self, path: str) -> bool:
        return self.full_path(path).exists()

    def size(self, path: str) -> int:
        return os.path.getsize(self.full_path(path))


# Module-level singleton — swap implementation here for cloud storage
def get_storage(base_dir: Path | None = None) -> LocalStorage:
    """Return the configured storage backend."""
    from ..config import settings
    return LocalStorage(base_dir or settings.storage_path)

