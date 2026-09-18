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

import mimetypes
import re
from pathlib import Path, PurePosixPath
from typing import Protocol, runtime_checkable

import httpx

from app.core.settings import get_settings

# Key content is attacker-controlled (it lands in a DB column and is later handed straight to
# the filesystem on Linux, where control characters, spaces and most unicode are legal in a
# filename) -- so each segment is checked against this allowlist rather than a denylist.
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")

# Windows' registry maps .csv to application/vnd.ms-excel (a legacy Excel association), which
# would otherwise leak through mimetypes.guess_type() on a Windows dev machine or CI runner.
# guess_type() checks the strict map first, so this must be registered strict=True (the
# default) to actually win over the registry-sourced entry.
mimetypes.add_type("text/csv", ".csv")


def _validate_key(key: str) -> None:
    """Shared by every StorageBackend: a hostile key must be rejected the same way

    regardless of which backend is configured. `LocalStorage` additionally resolves the
    key against its root to catch traversal; `SupabaseStorage` has no local filesystem to
    escape, but the object path is still built by string concatenation into a URL, so the
    same allowlist keeps a key from injecting `../`, a query string or another bucket path.
    """
    if not key or "\\" in key or ":" in key:
        raise ValueError(f"invalid storage key: {key!r}")

    parts = key.split("/")
    if key.startswith("/") or "" in parts or ".." in parts or "." in parts:
        raise ValueError(f"invalid storage key: {key!r}")
    if not all(_SAFE_SEGMENT.fullmatch(part) for part in parts):
        raise ValueError(f"invalid storage key: {key!r}")


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
        _validate_key(key)

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


class StorageError(RuntimeError):
    """The storage backend refused a request, or is not configured."""


class SupabaseStorage:
    """Supabase Storage (private bucket) over its REST API, using the service-role key.

    Endpoints (Supabase Storage API v1), all under `{supabase_url}/storage/v1`:
        upload    POST   /object/{bucket}/{key}   (header `x-upsert: true` to overwrite)
        download  GET    /object/{bucket}/{key}
        delete    DELETE /object/{bucket}/{key}

    The bucket is private: every one of these calls is authorised by the service-role key,
    which lives only on the backend (`docs/PLAN.md` §7). No public or signed URLs are
    handed out — files are streamed back through our own endpoints, which already enforce
    tenant isolation.
    """

    def __init__(
        self,
        supabase_url: str,
        service_key: str,
        bucket: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.bucket = bucket
        self._client = httpx.Client(
            base_url=f"{supabase_url.rstrip('/')}/storage/v1",
            headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
            timeout=timeout,
            transport=transport,
        )

    def _path(self, key: str) -> str:
        # Same allowlist as LocalStorage: a key is built straight into this URL path, so a
        # hostile key must be rejected identically regardless of which backend is active.
        _validate_key(key)
        return f"/object/{self.bucket}/{key.lstrip('/')}"

    @staticmethod
    def _fail(action: str, response: httpx.Response) -> StorageError:
        # response.text, never the request headers: the service key must never be logged.
        return StorageError(f"supabase {action} failed ({response.status_code}): {response.text}")

    def save(self, key: str, data: bytes) -> str:
        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        response = self._client.post(
            self._path(key),
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        if response.status_code >= 400:
            raise self._fail("upload", response)
        return key

    def read(self, key: str) -> bytes:
        response = self._client.get(self._path(key))
        if response.status_code >= 400:
            raise self._fail("download", response)
        return response.content

    def delete(self, key: str) -> None:
        response = self._client.delete(self._path(key))
        if response.status_code >= 400 and response.status_code != 404:
            raise self._fail("delete", response)


# F6(b): a SupabaseStorage instance owns an httpx.Client, which owns a real connection
# pool - building a fresh one on every get_storage() call (this function is deliberately
# NOT @lru_cache'd, see below) leaked a socket per call under load. This cache reuses the
# same SupabaseStorage/httpx.Client for a given (url, key, bucket) triple instead, so a
# process that stays on one Supabase project keeps exactly one pool for its lifetime.
_supabase_storage_cache: dict[tuple[str, str, str], "SupabaseStorage"] = {}


def get_storage() -> StorageBackend:
    """LocalStorage is deliberately built fresh every call (not cached): tests point
    `storage_root` at a fresh tmp_path per test, and LocalStorage holds no resource worth
    reusing. SupabaseStorage IS reused across calls with the same settings — see
    `_supabase_storage_cache` above.
    """
    settings = get_settings()
    if settings.storage_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_service_key:
            raise StorageError(
                "STORAGE_BACKEND=supabase needs SUPABASE_URL and SUPABASE_SERVICE_KEY"
            )
        cache_key = (settings.supabase_url, settings.supabase_service_key, settings.storage_bucket)
        cached = _supabase_storage_cache.get(cache_key)
        if cached is None:
            cached = SupabaseStorage(
                settings.supabase_url, settings.supabase_service_key, settings.storage_bucket
            )
            _supabase_storage_cache[cache_key] = cached
        return cached
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_root)
    raise ValueError(f"unknown storage_backend: {settings.storage_backend!r}")
