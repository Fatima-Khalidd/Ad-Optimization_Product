from app.core.settings import Settings

# The existing Stage 0 prod validator rejects sqlite DATABASE_URLs in prod (see
# test_settings.py::test_prod_rejects_sqlite_database_url), so BASE uses a postgres URL
# rather than sqlite - these tests exercise env="prod" and must stay compatible with that
# validator rather than accidentally weakening it.
BASE = {"database_url": "postgresql+psycopg://user:pw@host/db", "secret_key": "x" * 32}


def test_stage8_defaults_are_safe():
    settings = Settings(env="dev", **BASE)
    assert settings.sentry_dsn is None
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.max_request_mb == 25
    assert settings.supabase_url is None
    assert settings.supabase_service_key is None
    assert settings.storage_bucket == "ad-optimizer"


def test_cors_origins_parses_a_comma_separated_env_var(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, https://www.example.com/")
    settings = Settings(env="prod", **BASE)
    assert settings.cors_origins == ["https://app.example.com", "https://www.example.com"]


def test_cors_origins_accepts_a_single_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    assert Settings(env="prod", **BASE).cors_origins == ["https://app.example.com"]


def test_cors_origins_ignores_blank_entries(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com,,  ,https://b.example.com")
    settings = Settings(env="prod", **BASE)
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_cookie_secure_is_true_in_prod():
    assert Settings(env="prod", **BASE).cookie_secure is True


def test_cookie_secure_is_false_outside_prod():
    assert Settings(env="dev", **BASE).cookie_secure is False
    assert Settings(env="test", **BASE).cookie_secure is False


def test_supabase_values_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://abcdefgh.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-role-key")
    monkeypatch.setenv("STORAGE_BUCKET", "ad-optimizer-prod")
    settings = Settings(env="prod", **BASE)
    assert settings.supabase_url == "https://abcdefgh.supabase.co"
    assert settings.supabase_service_key == "service-role-key"
    assert settings.storage_bucket == "ad-optimizer-prod"
