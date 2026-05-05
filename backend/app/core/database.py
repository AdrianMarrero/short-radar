"""Database engine, session, and base."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
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


def _ensure_short_score_columns(engine_) -> None:
    """Idempotent bootstrap migration for short_scores.raw_score_data.

    The v2 redesign added a JSON column to ShortScore. SQLAlchemy's
    create_all() does NOT alter existing tables, so on environments
    where short_scores already exists we run a single ALTER TABLE.

    - PostgreSQL: ``raw_score_data JSONB DEFAULT NULL``
    - SQLite:     ``raw_score_data TEXT DEFAULT NULL`` (JSON serialized as TEXT)

    Wrapped in try/except so a redeploy never crashes if the column
    already exists or the dialect rejects the statement.
    """
    log = logging.getLogger(__name__)
    try:
        insp = inspect(engine_)
        if "short_scores" not in insp.get_table_names():
            return  # create_all() will handle it on first boot
        cols = {c["name"] for c in insp.get_columns("short_scores")}
        if "raw_score_data" in cols:
            return

        dialect = engine_.dialect.name
        if dialect == "postgresql":
            stmt = "ALTER TABLE short_scores ADD COLUMN raw_score_data JSONB"
        else:
            # SQLite + fallback
            stmt = "ALTER TABLE short_scores ADD COLUMN raw_score_data TEXT"

        with engine_.begin() as conn:
            conn.execute(text(stmt))
        log.info("bootstrap migration ok: added short_scores.raw_score_data (%s)", dialect)
    except Exception as e:  # noqa: BLE001
        # Never crash startup over a migration race. Log and continue.
        log.warning("short_scores.raw_score_data bootstrap skipped: %s", e)


def _ensure_fundamentals_columns(engine_) -> None:
    """Idempotent bootstrap migration for fundamentals additive columns.

    - ``updated_at``: used by the yfinance .info cache (7-day TTL).
    - v3 edge-factor columns: analyst targets + earnings revisions
      (``target_mean_price``, ``target_high_price``, ``target_low_price``,
      ``recommendation_mean``, ``num_analyst_opinions``,
      ``earnings_growth_quarterly``, ``earnings_growth_yoy``,
      ``revenue_growth``).

    Wrapped in try/except so a redeploy never crashes if a column already
    exists or the dialect rejects the statement.
    """
    log = logging.getLogger(__name__)
    try:
        insp = inspect(engine_)
        if "fundamentals" not in insp.get_table_names():
            return
        cols = {c["name"] for c in insp.get_columns("fundamentals")}

        dialect = engine_.dialect.name
        ts_type = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
        float_type = "DOUBLE PRECISION" if dialect == "postgresql" else "FLOAT"

        # Column-name -> SQL type
        wanted = {
            "updated_at": ts_type,
            "target_mean_price": float_type,
            "target_high_price": float_type,
            "target_low_price": float_type,
            "recommendation_mean": float_type,
            "num_analyst_opinions": float_type,
            "earnings_growth_quarterly": float_type,
            "earnings_growth_yoy": float_type,
            "revenue_growth": float_type,
        }

        missing = [(name, sql) for name, sql in wanted.items() if name not in cols]
        if not missing:
            return

        with engine_.begin() as conn:
            for name, sql in missing:
                try:
                    conn.execute(text(f"ALTER TABLE fundamentals ADD COLUMN {name} {sql}"))
                    log.info("bootstrap migration ok: added fundamentals.%s (%s)", name, dialect)
                except Exception as ie:  # noqa: BLE001
                    log.warning("fundamentals.%s bootstrap skipped: %s", name, ie)
    except Exception as e:  # noqa: BLE001
        log.warning("fundamentals bootstrap skipped: %s", e)


def init_db() -> None:
    """Create all tables. For MVP we skip Alembic and let SQLAlchemy create them."""
    from app.models import all_models  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
    _ensure_short_score_columns(engine)
    _ensure_fundamentals_columns(engine)
