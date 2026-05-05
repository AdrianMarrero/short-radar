"""Modelos para noticias, fundamentales, short interest y eventos macro."""
from __future__ import annotations

from datetime import datetime, date as DateType
from sqlalchemy import String, Text, Float, DateTime, Date, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NewsItem(Base):
    __tablename__ = "news_items"
    __table_args__ = (Index("ix_news_inst_pub", "instrument_id", "published_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("instruments.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    source: Mapped[str] = mapped_column(String(128), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")

    # Sentimiento entre -1 (muy negativa) y +1 (muy positiva)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    # Impacto entre 0 y 1
    impact_score: Mapped[float] = mapped_column(Float, default=0.0)
    # categoria libre: earnings, regulatory, downgrade, lawsuit, dilution, etc.
    category: Mapped[str] = mapped_column(String(64), default="")


class Fundamentals(Base):
    __tablename__ = "fundamentals"
    __table_args__ = (Index("ix_fund_inst_period", "instrument_id", "period", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id"), index=True)
    period: Mapped[str] = mapped_column(String(16))  # e.g. "2024-Q4", "TTM"

    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    cash: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_outstanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_sales: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)

    # v3 edge factors: analyst targets + earnings revisions
    target_mean_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_high_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_low_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    num_analyst_opinions: Mapped[float | None] = mapped_column(Float, nullable=True)
    earnings_growth_quarterly: Mapped[float | None] = mapped_column(Float, nullable=True)
    earnings_growth_yoy: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ShortData(Base):
    __tablename__ = "short_data"
    __table_args__ = (Index("ix_short_inst_date", "instrument_id", "date", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id"), index=True)
    date: Mapped[DateType] = mapped_column(Date, index=True)

    short_interest: Mapped[float | None] = mapped_column(Float, nullable=True)
    short_percent_float: Mapped[float | None] = mapped_column(Float, nullable=True)
    days_to_cover: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_to_borrow: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_available: Mapped[float | None] = mapped_column(Float, nullable=True)
    float_shares: Mapped[float | None] = mapped_column(Float, nullable=True)


class MacroEvent(Base):
    __tablename__ = "macro_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[DateType] = mapped_column(Date, index=True)
    region: Mapped[str] = mapped_column(String(32), default="GLOBAL")
    category: Mapped[str] = mapped_column(String(64), default="")  # rates, inflation, oil, fx, geopolitics
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text, default="")
    impact_score: Mapped[float] = mapped_column(Float, default=0.0)
    affected_sectors: Mapped[str] = mapped_column(String(512), default="")  # CSV de sectores
