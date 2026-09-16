from app.core.db import configure_engine, get_engine, make_engine, reset_engine


def test_configure_engine_binds_the_given_engine():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    try:
        configure_engine(engine)
        assert get_engine() is engine
    finally:
        reset_engine()


def test_reset_engine_makes_get_engine_lazily_recreate_from_settings():
    # Settings in the test env point at the same in-memory sqlite URL (see conftest.py),
    # so get_engine() after reset_engine() should build a *new*, equivalent engine
    # rather than raise or keep returning the old one.
    engine = make_engine("sqlite+pysqlite:///:memory:")
    try:
        configure_engine(engine)
        reset_engine()

        recreated = get_engine()

        assert recreated is not engine
        assert str(recreated.url) == "sqlite+pysqlite:///:memory:"
    finally:
        reset_engine()
