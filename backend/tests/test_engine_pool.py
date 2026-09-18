from app.core.db import make_engine

# A URL is enough: SQLAlchemy does not connect until the first query.
PG_URL = "postgresql+psycopg://user:pass@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"


def test_postgres_engine_is_sized_for_the_supabase_pooler():
    engine = make_engine(PG_URL)
    assert engine.dialect.name == "postgresql"
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 5
    assert engine.pool._recycle == 1800
    assert engine.pool._pre_ping is True


def test_sqlite_engine_is_untouched():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    assert engine.dialect.name == "sqlite"
    # -1 is SQLAlchemy's "never recycle" default: no pool tuning leaked onto SQLite.
    assert engine.pool._recycle == -1
    assert not hasattr(engine.pool, "_max_overflow")


def test_sqlite_still_allows_cross_thread_use():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("select 1").scalar() == 1


def test_a_plain_sqlite_file_url_is_also_treated_as_sqlite(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'x.db'}")
    assert engine.dialect.name == "sqlite"
    assert engine.pool._recycle == -1
