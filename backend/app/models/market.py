"""Modelos de datos de mercado: precios diarios e indicadores técnicos."""
from __future__ import annotations

from datetime import date as DateType
from sqlalchemy import Float, Date, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PriceDaily(Base):
    __tablename__ = "prices_daily"
    __table_args__ = (Index("ix_prices_inst_date", "instrument_id", "date", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id"), index=True)
    date: Mapped[DateType] = mapped_column(Date, index=True)
    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float | None] = mapped_column(Float, nullable=True)
    adjusted_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)


class TechnicalIndicators(Base):
    __tablename__ = "technical_indicators"
    __table_args__ = (Index("ix_tech_inst_date", "instrument_id", "date", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id"), index=True)
    date: Mapped[DateType] = mapped_column(Date, index=True)

    sma_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    sma_200: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_20: Mapped[float | None] = mapped_column(Float, nullable=True)
    ema_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    rsi_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd: Mapped[float | None] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[float | None] = mapped_column(Float, nullable=True)
    atr_14: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Niveles y estructura
    support_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    resistance_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_52w: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_52w: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Variaciones
    change_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_5d: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_6m: Mapped[float | None] = mapped_column(Float, nullable=True)
