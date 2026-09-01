from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_session_factory = None
_engine_url = None


def build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def get_engine():
    global _engine, _engine_url
    settings = get_settings()
    database_url = settings.sqlalchemy_database_url
    if _engine is None or _engine_url != database_url:
        _engine = build_engine(database_url)
        _engine_url = database_url
    return _engine


def get_session_factory():
    global _session_factory
    engine = get_engine()
    if _session_factory is None or _session_factory.kw["bind"] is not engine:
        _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return _session_factory


def reset_engine_state() -> None:
    global _engine, _session_factory, _engine_url
    _engine = None
    _session_factory = None
    _engine_url = None


def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
