from pathlib import Path

import pytest

from app.core.settings import get_settings
from app.services.storage import LocalStorage, get_storage


def test_save_returns_the_key_and_writes_the_bytes(tmp_path: Path):
    storage = LocalStorage(tmp_path)

    key = storage.save("uploads/7/abc.csv", b"date,spend\n2026-08-01,10\n")

    assert key == "uploads/7/abc.csv"
    assert (tmp_path / "uploads" / "7" / "abc.csv").read_bytes().startswith(b"date,spend")


def test_read_round_trips_and_delete_removes(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    storage.save("uploads/7/abc.csv", b"hello")

    assert storage.read("uploads/7/abc.csv") == b"hello"

    storage.delete("uploads/7/abc.csv")
    with pytest.raises(FileNotFoundError):
        storage.read("uploads/7/abc.csv")


def test_delete_is_idempotent(tmp_path: Path):
    LocalStorage(tmp_path).delete("uploads/7/never-existed.csv")  # must not raise


def test_save_overwrites_the_same_key(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    storage.save("uploads/7/abc.csv", b"first")
    storage.save("uploads/7/abc.csv", b"second")

    assert storage.read("uploads/7/abc.csv") == b"second"


@pytest.mark.parametrize("key", ["", "/etc/passwd", "uploads/../../secrets.csv", "../x.csv"])
def test_keys_that_escape_the_root_are_rejected(tmp_path: Path, key: str):
    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).save(key, b"x")


@pytest.mark.parametrize(
    "key",
    [
        "../secret",
        "/etc/passwd",
        "C:\\Windows\\x",
        "a/../../b",
        "uploads\\7\\abc.csv",
    ],
)
def test_additional_traversal_and_windows_specific_keys_are_rejected(tmp_path: Path, key: str):
    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).save(key, b"x")

    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).read(key)

    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).delete(key)


@pytest.mark.parametrize(
    "key",
    [
        "a\nb",
        "a\x00b",
        "a\tb",
        "has space.csv",
        "uploads/1/../x.csv",
    ],
)
def test_keys_with_unsafe_characters_are_rejected(tmp_path: Path, key: str):
    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).save(key, b"x")

    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).read(key)

    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).delete(key)


@pytest.mark.parametrize("key", ["uploads/7/abc.csv", "proofs/3/9f8e7d6c-1234.pdf"])
def test_contract_key_shapes_round_trip(tmp_path: Path, key: str):
    storage = LocalStorage(tmp_path)

    assert storage.save(key, b"payload") == key
    assert storage.read(key) == b"payload"

    storage.delete(key)
    with pytest.raises(FileNotFoundError):
        storage.read(key)


def test_path_for_returns_the_resolved_path_under_root(tmp_path: Path):
    storage = LocalStorage(tmp_path)

    assert storage.path_for("uploads/7/abc.csv") == tmp_path / "uploads" / "7" / "abc.csv"


def test_different_clients_keys_do_not_collide(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    storage.save("uploads/7/abc.csv", b"client-seven")
    storage.save("uploads/9/abc.csv", b"client-nine")

    assert storage.read("uploads/7/abc.csv") == b"client-seven"
    assert storage.read("uploads/9/abc.csv") == b"client-nine"


def test_get_storage_builds_local_storage_from_settings(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "files"))
    get_settings.cache_clear()

    storage = get_storage()

    assert isinstance(storage, LocalStorage)
    assert storage.root == tmp_path / "files"
    get_settings.cache_clear()


def test_get_storage_rejects_an_unknown_backend(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "dropbox")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="unknown storage_backend"):
        get_storage()

    get_settings.cache_clear()


def test_settings_defaults():
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.storage_backend == "local"
    assert settings.storage_root == "./storage"
    assert settings.max_upload_mb == 20
