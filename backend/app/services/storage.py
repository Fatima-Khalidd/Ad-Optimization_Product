"""Uploaded files live behind this interface: local disk now, S3-compatible in Stage 8.

docs/PLAN.md section 1 #9 — Railway and Render disks are wiped on redeploy, so nothing
outside this module may assume a filesystem. `save()` returns the *key*, and that key is
what goes into DB `file_path` columns, so the same row works against any backend.

Keys look like ``uploads/{client_id}/{sha256}.csv`` or ``proofs/{client_id}/{payment_id}.{ext}``:
POSIX-style relative paths, forward slashes only. Every entry point (`save`/`read`/`delete`)
routes through `LocalStorage._resolve`, which is the single place that rejects a key trying to
escape `root` -- via `..` segments, an absolute path, a drive letter, or a backslash (Windows
path separators would otherwise let a key smuggle a traversal past the POSIX-style checks).
"""

import re
from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable

from app.core.settings import get_settings

# Key content is attacker-controlled (it lands in a DB column and is later handed straight to
# the filesystem on Linux, where control characters, spaces and most unicode are legal in a
# filename) -- so each segment is checked against this allowlist rather than a denylist.
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")


@runtime_checkable
class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> str: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalStorage:
    """Dev and test backend. Keys are relative POSIX-style paths under `root`."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def _resolve(self, key: str) -> Path:
        if not key or "\\" in key or ":" in key:
            raise ValueError(f"invalid storage key: {key!r}")

        parts = key.split("/")
        if key.startswith("/") or "" in parts or ".." in parts or "." in parts:
            raise ValueError(f"invalid storage key: {key!r}")
        if not all(_SAFE_SEGMENT.fullmatch(part) for part in parts):
            raise ValueError(f"invalid storage key: {key!r}")

        root = self.root.resolve()
        candidate = (root / PurePosixPath(key)).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError(f"invalid storage key: {key!r}")
        return self.root / key

    def path_for(self, key: str) -> Path:
        return self._resolve(key)

    def save(self, key: str, data: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_bytes(data)
        tmp_path.replace(path)
        return key

    def read(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self._resolve(key).unlink(missing_ok=True)


def get_storage() -> StorageBackend:
    """Deliberately not cached: tests point `storage_root` at a fresh tmp_path per test."""
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_root)
    raise ValueError(f"unknown storage_backend: {settings.storage_backend!r}")
