"""Portfolio construction layer.

Surfaces real-time portfolio state (open trades, sector exposure, capital
remaining) and evaluates each ranking signal against that state to flag
issues like "cartera llena", "ya en cartera", concentración sectorial, or
capital insuficiente.

Warnings are MERGED into the score's existing ``warnings`` list — rows are
NEVER removed. The frontend renders them via WarningChips so the user sees
why a candidate is non-actionable for THEM today even if the signal itself
is otherwise strong.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models import Instrument, Trade


# --- Constants ---------------------------------------------------------------

MAX_POSITIONS = 5
MAX_SECTOR_EXPOSURE_PCT = 0.30  # 30% of capital per sector ceiling


# Warning codes (Spanish-readable; labels live in Badges.tsx).
W_CARTERA_LLENA = "cartera_llena"
W_YA_EN_CARTERA = "ya_en_cartera"
W_CONCENTRACION_SECTOR = "concentracion_sector"
W_CAPITAL_INSUFICIENTE = "capital_insuficiente"


# --- Dataclass ---------------------------------------------------------------


@dataclass
class PortfolioState:
    open_trades: list[Trade]
    # sector -> fraction of capital (0..1)
    sector_exposure_pct: dict[str, float] = field(default_factory=dict)
    # instrument_id -> sector for fast lookup of "ya en cartera" / sector match
    instrument_sectors: dict[int, str] = field(default_factory=dict)
    open_instrument_ids: set[int] = field(default_factory=set)
    total_invested_eur: float = 0.0
    capital_eur: float = 0.0

    @property
    def remaining_capital_eur(self) -> float:
        return max(0.0, self.capital_eur - self.total_invested_eur)


# --- Loader ------------------------------------------------------------------


def load_portfolio_state(db: Session, capital_eur: float) -> PortfolioState:
    """Snapshot the user's open trades + sector exposure.

    capital_eur is treated as the user's total bankroll. Sector exposure is
    expressed as fraction of capital_eur (NOT fraction of currently-invested
    money) so a 30% cap behaves the same regardless of how much cash is
    deployed today.
    """
    rows = (
        db.query(Trade, Instrument)
        .join(Instrument, Instrument.id == Trade.instrument_id)
        .filter(Trade.status == "open")
        .all()
    )

    open_trades: list[Trade] = []
    instrument_sectors: dict[int, str] = {}
    open_instrument_ids: set[int] = set()
    sector_invested_eur: dict[str, float] = {}
    total_invested_eur = 0.0

    for trade, inst in rows:
        open_trades.append(trade)
        sector = (inst.sector or "").strip() or "unknown"
        instrument_sectors[trade.instrument_id] = sector
        open_instrument_ids.add(trade.instrument_id)
        cap = float(trade.capital_eur or 0.0)
        total_invested_eur += cap
        sector_invested_eur[sector] = sector_invested_eur.get(sector, 0.0) + cap

    base = float(capital_eur) if capital_eur and capital_eur > 0 else 1.0
    sector_exposure_pct = {
        s: round(v / base, 4) for s, v in sector_invested_eur.items()
    }

    return PortfolioState(
        open_trades=open_trades,
        sector_exposure_pct=sector_exposure_pct,
        instrument_sectors=instrument_sectors,
        open_instrument_ids=open_instrument_ids,
        total_invested_eur=round(total_invested_eur, 2),
        capital_eur=float(capital_eur),
    )


# --- Evaluation --------------------------------------------------------------


def evaluate_signal_against_portfolio(
    *,
    instrument_id: int,
    sector: Optional[str],
    position_size_eur: Optional[float],
    portfolio: PortfolioState,
) -> list[str]:
    """Return the list of portfolio_warnings to merge into score.warnings.

    Inputs come from the ranking row (NOT a model — keep this layer pure):
      - instrument_id: ScoreOut.instrument_id
      - sector: ScoreOut.sector
      - position_size_eur: ScoreOut.position_size_eur (may be None)

    Order matters for UX: cartera_llena first (most blocking), ya_en_cartera
    second (specific match), concentracion_sector third (allocation), and
    capital_insuficiente last (sizing).
    """
    out: list[str] = []

    if len(portfolio.open_trades) >= MAX_POSITIONS:
        out.append(W_CARTERA_LLENA)

    if instrument_id in portfolio.open_instrument_ids:
        out.append(W_YA_EN_CARTERA)

    sec = (sector or "").strip() or "unknown"
    base = portfolio.capital_eur if portfolio.capital_eur > 0 else 1.0
    pos_pct = (float(position_size_eur or 0.0) / base) if base > 0 else 0.0
    current_sector_pct = float(portfolio.sector_exposure_pct.get(sec, 0.0))
    if (current_sector_pct + pos_pct) > MAX_SECTOR_EXPOSURE_PCT:
        out.append(W_CONCENTRACION_SECTOR)

    if (
        position_size_eur is not None
        and position_size_eur > 0
        and position_size_eur > portfolio.remaining_capital_eur
    ):
        out.append(W_CAPITAL_INSUFICIENTE)

    return out


def merge_warnings(existing: Iterable[str] | None, extra: Iterable[str]) -> list[str]:
    """Merge ``extra`` into ``existing`` preserving order, dropping duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for w in (existing or []):
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    for w in extra:
        if w in seen:
            continue
        seen.add(w)
        out.append(w)
    return out
