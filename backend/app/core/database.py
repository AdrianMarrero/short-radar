"""Database engine, session, and base."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite needs a connect arg for thread-safety; Postgres ignores it
connect_args = {"check_same_thread": False} if settings.effective_database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.effective_database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for jobs and scripts that don't go through FastAPI."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. For MVP we skip Alembic and let SQLAlchemy create them."""
    from app.models import all_models  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
