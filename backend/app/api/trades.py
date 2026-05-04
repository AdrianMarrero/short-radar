"""Operations journal endpoints — track real trades to measure if the system gives edge."""
from __future__ import annotations

import asyncio
from datetime import date as DateType, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.admin import require_admin
from app.api.ranking import _sanitize_floats
from app.api.schemas import (
    TradeIn, TradeCloseIn, TradeOut, TradeStatsOut, TradeStatsBucket,
)
from app.collectors.market_data import fetch_latest_price
from app.core.database import get_db
from app.core.logging import get_logger
from app.models import Instrument, PriceDaily, Trade

log = get_logger(__name__)

router = APIRouter(prefix="/api/trades", tags=["trades"])


# -------- Helpers --------


def _resolve_instrument(db: Session, payload: TradeIn) -> Instrument:
    if payload.instrument_id is not None:
        inst = db.query(Instrument).filter(Instrument.id == payload.instrument_id).first()
        if not inst:
            raise HTTPException(status_code=404, detail=f"Instrument {payload.instrument_id} not found")
        return inst
    if payload.ticker:
        ticker = payload.ticker.upper()
        inst = db.query(Instrument).filter(Instrument.ticker == ticker).first()
        if not inst:
            inst = db.query(Instrument).filter(Instrument.ticker == payload.ticker).first()
        if not inst:
            raise HTTPException(status_code=404, detail=f"Ticker {payload.ticker} not found")
        return inst
    raise HTTPException(status_code=400, detail="Either instrument_id or ticker is required")


def _last_close_for(db: Session, instrument_id: int) -> float | None:
    row = (
        db.query(PriceDaily.close)
        .filter(PriceDaily.instrument_id == instrument_id)
        .order_by(PriceDaily.date.desc())
        .first()
    )
    return float(row[0]) if row and row[0] is not None else None


def _last_closes_for(db: Session, instrument_ids: list[int]) -> dict[int, float]:
    if not instrument_ids:
        return {}
    rows = (
        db.query(PriceDaily.instrument_id, PriceDaily.close, PriceDaily.date)
        .filter(PriceDaily.instrument_id.in_(instrument_ids))
        .order_by(PriceDaily.instrument_id, PriceDaily.date.desc())
        .all()
    )
    seen: dict[int, float] = {}
    for inst_id, close, _ in rows:
        if inst_id not in seen and close is not None:
            seen[inst_id] = float(close)
    return seen


def _build_trade_out(trade: Trade, inst: Instrument, current_price: float | None) -> TradeOut:
    days_held: int | None = None
    pnl_pct_live: float | None = None
    pnl_eur_live: float | None = None

    if trade.status == "open":
        anchor_date = trade.exit_date or DateType.today()
        days_held = max((anchor_date - trade.entry_date).days, 0)
        if current_price is not None and trade.entry_price:
            pnl_pct_live = (current_price - trade.entry_price) / trade.entry_price * 100.0
            pnl_eur_live = trade.capital_eur * pnl_pct_live / 100.0
    elif trade.exit_date is not None:
        days_held = max((trade.exit_date - trade.entry_date).days, 0)

    return TradeOut(
        id=trade.id,
        instrument_id=trade.instrument_id,
        ticker=inst.ticker,
        name=inst.name or inst.ticker,
        setup_type=trade.setup_type or "",
        profile=trade.profile or "conservative",
        capital_eur=trade.capital_eur,
        entry_price=trade.entry_price,
        entry_date=trade.entry_date,
        stop_price=trade.stop_price,
        target_1=trade.target_1,
        target_2=trade.target_2,
        exit_price=trade.exit_price,
        exit_date=trade.exit_date,
        status=trade.status,
        notes=trade.notes or "",
        pnl_pct=trade.pnl_pct,
        pnl_eur=trade.pnl_eur,
        created_at=trade.created_at,
        updated_at=trade.updated_at,
        current_price=current_price,
        pnl_pct_live=pnl_pct_live,
        pnl_eur_live=pnl_eur_live,
        days_held=days_held,
    )


def _classify_close(entry: float, exit_: float, stop: float | None) -> str:
    if stop is not None and exit_ <= stop:
        return "stopped"
    if exit_ > entry:
        return "closed_win"
    return "closed_loss"


# -------- CRUD --------


@router.post("", response_model=TradeOut)
def create_trade(
    payload: TradeIn,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    if payload.capital_eur <= 0:
        raise HTTPException(status_code=400, detail="capital_eur must be > 0")
    if payload.entry_price <= 0:
        raise HTTPException(status_code=400, detail="entry_price must be > 0")

    inst = _resolve_instrument(db, payload)
    profile = payload.profile if payload.profile in ("conservative", "aggressive") else "conservative"

    trade = Trade(
        instrument_id=inst.id,
        setup_type=payload.setup_type or "",
        profile=profile,
        capital_eur=payload.capital_eur,
        entry_price=payload.entry_price,
        entry_date=payload.entry_date or DateType.today(),
        stop_price=payload.stop_price,
        target_1=payload.target_1,
        target_2=payload.target_2,
        notes=payload.notes or "",
        status="open",
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)

    current_price = _last_close_for(db, inst.id)
    return _build_trade_out(trade, inst, current_price)


@router.get("", response_model=list[TradeOut])
def list_trades(
    status: Optional[str] = Query(None, description="open / closed / all (default: all)"),
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    q = db.query(Trade, Instrument).join(Instrument, Instrument.id == Trade.instrument_id)
    if status == "open":
        q = q.filter(Trade.status == "open")
    elif status == "closed":
        q = q.filter(Trade.status.in_(["closed_win", "closed_loss", "stopped"]))

    rows = q.order_by(Trade.entry_date.desc(), Trade.id.desc()).all()
    if not rows:
        return []

    inst_ids = list({t.instrument_id for t, _ in rows})
    last_closes = _last_closes_for(db, inst_ids)

    return [_build_trade_out(t, i, last_closes.get(t.instrument_id)) for t, i in rows]


@router.get("/stats", response_model=TradeStatsOut)
def trade_stats(
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    trades = db.query(Trade).all()
    total = len(trades)
    open_trades = [t for t in trades if t.status == "open"]
    closed_trades = [t for t in trades if t.status != "open"]
    n_open = len(open_trades)
    n_closed = len(closed_trades)

    wins = [t for t in closed_trades if (t.pnl_pct or 0) > 0]
    win_rate = (len(wins) / n_closed * 100.0) if n_closed else 0.0

    closed_returns = [t.pnl_pct for t in closed_trades if t.pnl_pct is not None]
    avg_return = (sum(closed_returns) / len(closed_returns)) if closed_returns else 0.0
    total_pnl_eur = sum((t.pnl_eur or 0.0) for t in closed_trades)

    durations = []
    for t in closed_trades:
        if t.exit_date and t.entry_date:
            durations.append(max((t.exit_date - t.entry_date).days, 0))
    avg_days_held = (sum(durations) / len(durations)) if durations else 0.0

    best = max(closed_trades, key=lambda t: t.pnl_pct or float("-inf"), default=None)
    worst = min(closed_trades, key=lambda t: t.pnl_pct or float("inf"), default=None)

    inst_map: dict[int, str] = {}
    if best or worst:
        ids = [t.instrument_id for t in (best, worst) if t]
        if ids:
            for inst in db.query(Instrument).filter(Instrument.id.in_(ids)).all():
                inst_map[inst.id] = inst.ticker

    def _bucket(group: list[Trade]) -> TradeStatsBucket:
        gc = [t for t in group if t.status != "open"]
        gw = [t for t in gc if (t.pnl_pct or 0) > 0]
        rets = [t.pnl_pct for t in gc if t.pnl_pct is not None]
        return TradeStatsBucket(
            n=len(group),
            n_closed=len(gc),
            win_rate_pct=(len(gw) / len(gc) * 100.0) if gc else 0.0,
            avg_return_pct=(sum(rets) / len(rets)) if rets else 0.0,
            total_pnl_eur=sum((t.pnl_eur or 0.0) for t in gc),
        )

    by_setup_groups: dict[str, list[Trade]] = {}
    by_profile_groups: dict[str, list[Trade]] = {}
    for t in trades:
        by_setup_groups.setdefault(t.setup_type or "unknown", []).append(t)
        by_profile_groups.setdefault(t.profile or "unknown", []).append(t)

    return TradeStatsOut(
        total=total,
        open=n_open,
        closed=n_closed,
        win_rate_pct=round(win_rate, 2),
        avg_return_pct=round(avg_return, 2),
        avg_days_held=round(avg_days_held, 1),
        total_pnl_eur=round(total_pnl_eur, 2),
        best_trade_pct=round(best.pnl_pct, 2) if best and best.pnl_pct is not None else None,
        worst_trade_pct=round(worst.pnl_pct, 2) if worst and worst.pnl_pct is not None else None,
        best_trade_ticker=inst_map.get(best.instrument_id) if best else None,
        worst_trade_ticker=inst_map.get(worst.instrument_id) if worst else None,
        by_setup={k: _bucket(v) for k, v in by_setup_groups.items()},
        by_profile={k: _bucket(v) for k, v in by_profile_groups.items()},
    )


@router.post("/refresh-prices")
async def refresh_prices(
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    """Fetch LIVE intraday prices for all open trades on demand.

    Reuses the curl_cffi yfinance session from market_data.py — does NOT
    create a new client. The live price is request-scoped: nothing gets
    persisted to prices_daily, so the daily close pipeline is untouched.

    Per-ticker timeout: 5s via asyncio.wait_for. Failures fall back to the
    last close in prices_daily so the response is always complete.
    """
    rows = (
        db.query(Trade, Instrument)
        .join(Instrument, Instrument.id == Trade.instrument_id)
        .filter(Trade.status == "open")
        .all()
    )

    if not rows:
        payload = {
            "trades": [],
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "live_count": 0,
            "fallback_count": 0,
        }
        return JSONResponse(content=_sanitize_floats(payload))

    # Unique tickers per instrument_id (multiple open trades may share a ticker).
    ticker_by_inst: dict[int, str] = {}
    for trade, inst in rows:
        ticker_by_inst[inst.id] = inst.ticker

    # Fetch each unique ticker's live price with a 5s soft timeout.
    live_prices: dict[int, float] = {}

    async def _fetch_one(inst_id: int, ticker: str) -> tuple[int, float | None]:
        try:
            price = await asyncio.wait_for(
                asyncio.to_thread(fetch_latest_price, ticker, 5.0),
                timeout=5.0,
            )
            return inst_id, price
        except asyncio.TimeoutError:
            log.warning("refresh-prices: timeout for %s", ticker)
            return inst_id, None
        except Exception as e:
            log.warning("refresh-prices: failed for %s: %s", ticker, e)
            return inst_id, None

    results = await asyncio.gather(
        *[_fetch_one(iid, tkr) for iid, tkr in ticker_by_inst.items()],
        return_exceptions=False,
    )
    for inst_id, price in results:
        if price is not None:
            live_prices[inst_id] = price

    # Build TradeOut list — fall back to last close on miss.
    trades_out: list[dict] = []
    live_count = 0
    fallback_count = 0
    for trade, inst in rows:
        live = live_prices.get(inst.id)
        if live is not None:
            current_price = live
            live_count += 1
        else:
            current_price = _last_close_for(db, inst.id)
            fallback_count += 1
        out = _build_trade_out(trade, inst, current_price)
        trades_out.append(out.model_dump(mode="json"))

    payload = {
        "trades": trades_out,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "live_count": live_count,
        "fallback_count": fallback_count,
    }
    return JSONResponse(content=_sanitize_floats(payload))


@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    inst = db.query(Instrument).filter(Instrument.id == trade.instrument_id).first()
    if not inst:
        raise HTTPException(status_code=500, detail="Instrument missing for trade")
    current_price = _last_close_for(db, inst.id)
    return _build_trade_out(trade, inst, current_price)


@router.patch("/{trade_id}/close", response_model=TradeOut)
def close_trade(
    trade_id: int,
    payload: TradeCloseIn,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    if trade.status != "open":
        raise HTTPException(status_code=409, detail="Trade is already closed")
    if payload.exit_price <= 0:
        raise HTTPException(status_code=400, detail="exit_price must be > 0")

    trade.exit_price = payload.exit_price
    trade.exit_date = payload.exit_date or DateType.today()
    trade.pnl_pct = (trade.exit_price - trade.entry_price) / trade.entry_price * 100.0
    trade.pnl_eur = trade.capital_eur * trade.pnl_pct / 100.0
    trade.status = _classify_close(trade.entry_price, trade.exit_price, trade.stop_price)

    if payload.notes:
        trade.notes = (trade.notes + "\n" + payload.notes).strip() if trade.notes else payload.notes

    db.commit()
    db.refresh(trade)

    inst = db.query(Instrument).filter(Instrument.id == trade.instrument_id).first()
    current_price = _last_close_for(db, inst.id) if inst else None
    return _build_trade_out(trade, inst, current_price)


@router.delete("/{trade_id}")
def delete_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    _admin = Depends(require_admin),
):
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    db.delete(trade)
    db.commit()
    return {"status": "deleted", "id": trade_id}
