from pathlib import Path

import httpx
import pytest

from app.core.settings import get_settings
from app.services.storage import LocalStorage, StorageError, SupabaseStorage, get_storage

URL = "https://abcdefgh.supabase.co"
KEY = "service-role-key"
BUCKET = "ad-optimizer"


def _storage(handler) -> SupabaseStorage:
    return SupabaseStorage(URL, KEY, BUCKET, transport=httpx.MockTransport(handler))


def test_save_posts_to_the_object_endpoint_and_returns_the_key():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"Key": f"{BUCKET}/uploads/7/abc.csv"})

    returned = _storage(handler).save("uploads/7/abc.csv", b"date,spend\n")

    assert returned == "uploads/7/abc.csv"
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"
    assert request.content == b"date,spend\n"


def test_save_sends_the_service_key_and_upsert_and_content_type():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    _storage(handler).save("uploads/7/abc.csv", b"x")

    headers = seen[0].headers
    assert headers["authorization"] == f"Bearer {KEY}"
    assert headers["apikey"] == KEY
    assert headers["x-upsert"] == "true"
    assert headers["content-type"] == "text/csv"


def test_save_guesses_pdf_and_falls_back_to_octet_stream():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    storage = _storage(handler)
    storage.save("reports/7/run-3.pdf", b"%PDF-")
    storage.save("proofs/7/9.bin", b"\x00")

    assert seen[0].headers["content-type"] == "application/pdf"
    assert seen[1].headers["content-type"] == "application/octet-stream"


def test_read_gets_the_object_and_returns_its_bytes():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"date,spend\n2026-01-01,100\n")

    data = _storage(handler).read("uploads/7/abc.csv")

    assert data == b"date,spend\n2026-01-01,100\n"
    assert seen[0].method == "GET"
    assert str(seen[0].url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"


def test_delete_issues_a_delete():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"message": "Successfully deleted"})

    _storage(handler).delete("uploads/7/abc.csv")

    assert seen[0].method == "DELETE"
    assert str(seen[0].url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"


def test_delete_tolerates_a_missing_object():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found"})

    _storage(handler).delete("uploads/7/gone.csv")  # must not raise


def test_a_failed_upload_raises_storage_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "new row violates row-level security"})

    with pytest.raises(StorageError, match="403"):
        _storage(handler).save("uploads/7/abc.csv", b"x")


def test_a_missing_object_raises_storage_error_on_read():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found"})

    with pytest.raises(StorageError, match="404"):
        _storage(handler).read("uploads/7/missing.csv")


def test_the_service_key_is_never_in_the_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(StorageError) as excinfo:
        _storage(handler).save("uploads/7/abc.csv", b"x")
    assert KEY not in str(excinfo.value)


def test_a_trailing_slash_on_the_supabase_url_does_not_double_up():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    SupabaseStorage(f"{URL}/", KEY, BUCKET, transport=httpx.MockTransport(handler)).save(
        "uploads/7/abc.csv", b"x"
    )

    assert str(seen[0].url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"


def test_local_storage_round_trips_through_its_save_return_value(tmp_path: Path):
    """The contract SupabaseStorage must match: whatever save() returns, read() accepts."""
    storage = LocalStorage(tmp_path)
    returned = storage.save("uploads/7/abc.csv", b"hello")
    assert storage.read(returned) == b"hello"


def test_get_storage_returns_local_by_default(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    assert isinstance(get_storage(), LocalStorage)
    get_settings.cache_clear()


def test_get_storage_returns_supabase_when_configured(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", KEY)
    monkeypatch.setenv("STORAGE_BUCKET", BUCKET)
    get_settings.cache_clear()
    storage = get_storage()
    assert isinstance(storage, SupabaseStorage)
    assert storage.bucket == BUCKET
    get_settings.cache_clear()


def test_get_storage_refuses_supabase_without_credentials(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(StorageError, match="SUPABASE_URL"):
        get_storage()
    get_settings.cache_clear()


def test_get_storage_reuses_the_same_supabase_client_for_the_same_settings(monkeypatch):
    """F6(b): get_storage() must not build (and leak) a fresh httpx.Client on every call."""
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", KEY)
    monkeypatch.setenv("STORAGE_BUCKET", BUCKET)
    get_settings.cache_clear()

    first = get_storage()
    second = get_storage()

    assert first is second
    get_settings.cache_clear()


def test_get_storage_returns_a_different_client_for_a_different_bucket(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", KEY)
    monkeypatch.setenv("STORAGE_BUCKET", "a-different-bucket")
    get_settings.cache_clear()

    storage = get_storage()

    assert storage.bucket == "a-different-bucket"
    get_settings.cache_clear()
