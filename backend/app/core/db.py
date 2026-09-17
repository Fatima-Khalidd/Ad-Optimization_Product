from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import get_settings

# Deterministic constraint names so Alembic can diff and drop them by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def configure_engine(engine: Engine) -> None:
    """Bind the module to a specific engine (tests, or a custom startup path)."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)


def reset_engine() -> None:
    """Forget the configured engine so the next get_engine() call rebuilds it."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


def get_engine() -> Engine:
    if _engine is None:
        configure_engine(make_engine(get_settings().database_url))
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """A session outside the request cycle: background tasks, scripts, the CLI.

    `get_session()` is a FastAPI dependency and its session is closed before background
    tasks run, so anything that runs after the response must open its own. Commits on a
    clean exit, rolls back (leaving no rows) if the block raises.
    """
    get_engine()
    if _session_factory is None:
        raise RuntimeError("engine not configured")
    with _session_factory() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed.

    Does NOT commit. Callers (routers/services) must commit their own writes — an
    uncommitted change is silently discarded when the request ends, it is not an error.
    """
    get_engine()
    if _session_factory is None:
        raise RuntimeError("engine not configured")
    with _session_factory() as session:
        yield session
