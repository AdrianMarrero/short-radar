"""Trade model: registro del diario de operaciones del usuario."""
from __future__ import annotations

from datetime import datetime, date as DateType
from sqlalchemy import String, Text, Float, DateTime, Date, Integer, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Trade(Base):
    """Operación real registrada por el usuario.

    Independiente de ShortScore: ShortScore es la idea generada por el sistema,
    Trade es la ejecución real (con su capital, su entry real, su exit real).
    """
    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_status_entry_date", "status", "entry_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(Integer, ForeignKey("instruments.id"), index=True)

    # Capturados desde el ShortScore activo en el momento de abrir
    setup_type: Mapped[str] = mapped_column(String(32), default="")
    profile: Mapped[str] = mapped_column(String(16), default="conservative")  # conservative / aggressive

    # Plan de entrada
    capital_eur: Mapped[float] = mapped_column(Float, default=0.0)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_date: Mapped[DateType] = mapped_column(Date, index=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_1: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_2: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Cierre (nullable mientras la operación siga abierta)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_date: Mapped[DateType | None] = mapped_column(Date, nullable=True)

    # Estado: open / closed_win / closed_loss / stopped
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)

    notes: Mapped[str] = mapped_column(Text, default="")

    # Resultado calculado al cerrar
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_eur: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
