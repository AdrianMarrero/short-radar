"""Modelos para los scores diarios y las alertas del usuario."""
from __future__ import annotations

from datetime import datetime, date as DateType
from sqlalchemy import String, Text, Float, DateTime, Date, Integer, ForeignKey, Index, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShortScore(Base):
    __tablename__ = "short_scores"
    __table_args__ = (Index("ix_score_inst_date", "instrument_id", "date", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id"), index=True)
    date: Mapped[DateType] = mapped_column(Date, index=True)

    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    technical_score: Mapped[float] = mapped_column(Float, default=0.0)
    news_score: Mapped[float] = mapped_column(Float, default=0.0)
    fundamental_score: Mapped[float] = mapped_column(Float, default=0.0)
    macro_score: Mapped[float] = mapped_column(Float, default=0.0)
    squeeze_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Tipo de setup: deterioration, event, technical, overextension, avoid_squeeze
    setup_type: Mapped[str] = mapped_column(String(32), default="technical")
    # low / medium / high
    conviction: Mapped[str] = mapped_column(String(16), default="medium")
    horizon: Mapped[str] = mapped_column(String(16), default="swing")  # intraday/swing/positional

    # Plan de trade
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_2: Mapped[float | None] = mapped_column(Float, nullable=True)

    invalidation_reason: Mapped[str] = mapped_column(Text, default="")
    llm_explanation: Mapped[str] = mapped_column(Text, default="")
    # JSON serializado con los componentes que dispararon el score
    signals_json: Mapped[str] = mapped_column(Text, default="{}")

    # v2 redesign: tier/category/factor_scores/multipliers/warnings/explanation
    # Stored as JSON (PG: native JSON, SQLite: TEXT) — see core.database
    # _ensure_short_score_columns() for the bootstrap migration.
    raw_score_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("instruments.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    alert_type: Mapped[str] = mapped_column(String(64))  # score_threshold, support_break, top10, news_negative
    condition: Mapped[str] = mapped_column(String(255), default="")
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active, triggered, paused
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")


class JobRun(Base):
    """Auditoría de ejecuciones del job diario."""
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running/ok/error
    instruments_processed: Mapped[int] = mapped_column(Integer, default=0)
    scores_generated: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    triggered_by: Mapped[str] = mapped_column(String(32), default="manual")  # manual/scheduler
