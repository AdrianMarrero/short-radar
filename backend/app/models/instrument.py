"""Instrument model: el universo de valores que la app sigue."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import String, Boolean, Float, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Instrument(Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    exchange: Mapped[str] = mapped_column(String(32), index=True)  # NASDAQ, NYSE, IBEX, DAX, CAC, FTSE
    country: Mapped[str] = mapped_column(String(8), default="US")
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    sector: Mapped[str] = mapped_column(String(64), default="")
    industry: Mapped[str] = mapped_column(String(128), default="")
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Instrument {self.ticker} ({self.exchange})>"
