"""Vercel hosting: detection, the defaults it switches on, and the misconfigurations it refuses."""

import logging

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import NullPool

import app.core.db as db_module
from app.core.db import make_engine
from app.core.settings import Settings
from app.main import _warn_on_per_instance_rate_limit

PG_URL = "postgresql+psycopg://user:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"


@pytest.fixture(autouse=True)
def _not_on_vercel(monkeypatch):
    for name in ("VERCEL", "SERVERLESS", "ANALYSIS_DISPATCH", "STORAGE_BACKEND"):
        monkeypatch.delenv(name, raising=False)


def test_a_long_lived_server_runs_analyses_in_the_background():
    settings = Settings()
    assert settings.serverless is False
    assert settings.analysis_dispatch == "background"


def test_vercel_is_detected_and_runs_analyses_inline(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    settings = Settings(storage_backend="supabase")
    assert settings.serverless is True
    assert settings.analysis_dispatch == "inline"


def test_an_explicit_dispatch_mode_wins_over_detection(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("ANALYSIS_DISPATCH", "background")
    assert Settings(storage_backend="supabase").analysis_dispatch == "background"


def test_serverless_refuses_local_file_storage():
    with pytest.raises(ValidationError, match="STORAGE_BACKEND=supabase"):
        Settings(serverless=True, storage_backend="local")


def test_serverless_postgres_engine_holds_no_pool():
    engine = make_engine(PG_URL, serverless=True)
    assert isinstance(engine.pool, NullPool)


def test_serverless_psycopg_engine_disables_prepared_statements(monkeypatch):
    # Supabase's transaction pooler cannot keep prepared statements between transactions.
    captured: dict = {}
    monkeypatch.setattr(db_module, "create_engine", lambda url, **kwargs: captured.update(kwargs))
    make_engine(PG_URL, serverless=True)
    assert captured["connect_args"] == {"prepare_threshold": None}


def test_in_memory_rate_limit_on_serverless_is_warned_about(caplog):
    settings = Settings(serverless=True, storage_backend="supabase")
    with caplog.at_level(logging.WARNING, logger="app.main"):
        _warn_on_per_instance_rate_limit(settings)
    assert "RATE_LIMIT_STORAGE_URI" in caplog.text


def test_a_shared_rate_limit_store_is_not_warned_about(caplog):
    settings = Settings(
        serverless=True, storage_backend="supabase", rate_limit_storage_uri="redis://host:6379"
    )
    with caplog.at_level(logging.WARNING, logger="app.main"):
        _warn_on_per_instance_rate_limit(settings)
    assert caplog.text == ""
