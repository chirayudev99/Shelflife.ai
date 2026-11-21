"""SQLAlchemy engine and session factory for direct Postgres access."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_async_session_resources(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=_connect_args(database_url),
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _connect_args(database_url: str) -> dict[str, int | None]:
    if make_url(database_url).port == 6543:
        return {"prepare_threshold": None}
    return {}


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        database_url = settings.sqlalchemy_database_url
        _engine = create_engine(
            database_url,
            connect_args=_connect_args(database_url),
        )
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def get_session() -> Iterator[Session]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
    finally:
        session.close()
