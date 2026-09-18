import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.settings import get_settings
from app.models import AdDataUpload, AnalysisRun, Client, User


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """Point the global engine at a throwaway file-backed SQLite database.

    A file, not :memory:, because execute_run() opens its own session and therefore its
    own connection - an in-memory database would be empty from that connection's view.
    """
    import app.core.db as db_module

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'seed.db'}")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password-123")
    get_settings.cache_clear()
    db_module._engine = None
    db_module._session_factory = None

    db_module.Base.metadata.create_all(db_module.get_engine())
    yield db_module.get_engine()

    db_module._engine = None
    db_module._session_factory = None
    get_settings.cache_clear()


def test_seed_creates_a_demo_client_with_an_approved_run(seeded_db):
    from scripts.seed_demo import main

    assert main() == 0

    with Session(seeded_db) as session:
        demo = session.scalars(select(User).where(User.email == "demo@example.com")).one()
        assert demo.role == "client"
        client = session.scalars(select(Client).where(Client.user_id == demo.id)).one()

        upload = session.scalars(
            select(AdDataUpload).where(AdDataUpload.client_id == client.id)
        ).one()
        assert upload.status == "validated"
        assert upload.row_count > 0

        run = session.scalars(select(AnalysisRun).where(AnalysisRun.client_id == client.id)).one()
        assert run.status == "done"
        assert run.review_status == "approved"
        assert run.headline_waste is not None and run.headline_waste > 0


def test_seed_also_creates_the_admin_that_approves_the_run(seeded_db):
    from scripts.seed_demo import main

    assert main() == 0

    with Session(seeded_db) as session:
        admin = session.scalars(select(User).where(User.email == "admin@example.com")).one()
        assert admin.role == "admin"
        run = session.scalars(select(AnalysisRun)).one()
        assert run.reviewed_by == admin.id


def test_seed_is_idempotent(seeded_db):
    from scripts.seed_demo import main

    assert main() == 0
    assert main() == 0

    with Session(seeded_db) as session:
        assert len(session.scalars(select(User)).all()) == 2  # demo client + admin
        assert len(session.scalars(select(Client)).all()) == 1
        assert len(session.scalars(select(AdDataUpload)).all()) == 1
        assert len(session.scalars(select(AnalysisRun)).all()) == 1


def test_seed_refuses_to_run_without_a_password(seeded_db, monkeypatch, capsys):
    from scripts.seed_demo import main

    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    assert main() == 2
    assert "DEMO_PASSWORD" in capsys.readouterr().err


def test_seed_refuses_to_run_in_prod(seeded_db, monkeypatch, capsys):
    from scripts.seed_demo import main

    # Settings itself refuses ENV=prod with a sqlite DATABASE_URL or the default
    # SECRET_KEY, so satisfy those first to isolate the seed script's own prod guard.
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@localhost:5432/does-not-exist")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    get_settings.cache_clear()

    assert main() == 2
    assert "prod" in capsys.readouterr().err.lower()

    with Session(seeded_db) as session:
        assert session.scalars(select(User)).first() is None
