"""Daily pipeline job.

Steps:
  1. Make sure all instruments in the universe exist in DB.
  2. Pull macro RSS news, classify, persist.
  3. For each instrument:
     a. Fetch price history (1y), persist last 30 days of OHLCV.
     b. Compute & persist technical indicators.
     c. Fetch & persist company info (fundamentals + short data).
     d. Fetch & persist company news (sentiment-tagged).
     e. Score & persist.
  4. Generate LLM explanation for top N candidates.

Designed to run within Render's free 90-second exec window via batched processing
when triggered by HTTP. The internal scheduler version processes the full
universe.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, date as DateType, timedelta
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.collectors.universe import DELISTED_TICKERS, MARKETS, all_tickers
from app.collectors.market_data import (
    fetch_history,
    fetch_info_cached,
    fetch_news_yf,
    fetch_insider_transactions,
)
from app.collectors.macro import fetch_macro_news, classify_macro_item
from app.collectors.sentiment import analyze_news
from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging import get_logger
from app.models import (
    Instrument, PriceDaily, TechnicalIndicators, NewsItem, Fundamentals,
    ShortData, MacroEvent, ShortScore, JobRun,
)
from app.scoring.engine import compute_final_score
from app.scoring.technicals import compute_technical_snapshot
from app.scoring.edge_factors import detect_macro_regime
from app.services.llm import explain

settings = get_settings()
log = get_logger(__name__)


# ---------------- Setup helpers ----------------

def ensure_instruments(db: Session) -> dict[str, Instrument]:
    """Idempotent: insert any missing instruments, return ticker->Instrument map."""
    existing = {i.ticker: i for i in db.query(Instrument).all()}
    new_count = 0
    for ticker, exchange, country, currency in all_tickers():
        if ticker in existing:
            continue
        inst = Instrument(
            ticker=ticker,
            exchange=exchange,
            country=country,
            currency=currency,
        )
        db.add(inst)
        existing[ticker] = inst
        new_count += 1
    if new_count:
        db.flush()
        log.info("inserted %d new instruments", new_count)
    return existing


def collect_macro(db: Session) -> list[MacroEvent]:
    """Collect & persist today's macro events. Returns the list."""
    items = fetch_macro_news(max_per_feed=10)
    today = DateType.today()
    persisted: list[MacroEvent] = []

    # Limpieza simple: borra eventos de más de 14 días
    cutoff = today - timedelta(days=14)
    db.query(MacroEvent).filter(MacroEvent.date < cutoff).delete()

    for it in items:
        category, sectors, impact = classify_macro_item(it["title"], it["summary"])
        if impact < 0.2:
            continue  # sin keyword macro relevante
        ev = MacroEvent(
            date=it["published_at"].date() if isinstance(it["published_at"], datetime) else today,
            region="GLOBAL",
            category=category,
            title=it["title"][:500],
            summary=it["summary"][:1000],
            impact_score=impact,
            affected_sectors=",".join(sectors),
        )
        db.add(ev)
        persisted.append(ev)

    log.info("macro events collected: %d", len(persisted))
    return persisted


# ---------------- Per-instrument processing ----------------

def upsert_prices(db: Session, instrument_id: int, df: pd.DataFrame) -> None:
    """Persist last 60 days of OHLCV (idempotent)."""
    tail = df.tail(60)
    existing_dates = set(
        d for (d,) in db.query(PriceDaily.date)
        .filter(PriceDaily.instrument_id == instrument_id)
        .filter(PriceDaily.date >= tail.index.min().date())
        .all()
    )
    for ts, row in tail.iterrows():
        d = ts.date() if hasattr(ts, "date") else ts
        if d in existing_dates:
            continue
        db.add(PriceDaily(
            instrument_id=instrument_id,
            date=d,
            open=float(row.get("open", 0) or 0) or None,
            high=float(row.get("high", 0) or 0) or None,
            low=float(row.get("low", 0) or 0) or None,
            close=float(row.get("close", 0) or 0) or None,
            adjusted_close=float(row.get("adj close", row.get("close", 0)) or 0) or None,
            volume=float(row.get("volume", 0) or 0) or None,
        ))


def upsert_technicals(db: Session, instrument_id: int, snap, today: DateType) -> None:
    if snap is None:
        return
    existing = (
        db.query(TechnicalIndicators)
        .filter(TechnicalIndicators.instrument_id == instrument_id)
        .filter(TechnicalIndicators.date == today)
        .first()
    )
    if existing:
        rec = existing
    else:
        rec = TechnicalIndicators(instrument_id=instrument_id, date=today)
        db.add(rec)
    rec.sma_20 = snap.sma_20
    rec.sma_50 = snap.sma_50
    rec.sma_100 = snap.sma_100
    rec.sma_200 = snap.sma_200
    rec.ema_20 = snap.ema_20
    rec.ema_50 = snap.ema_50
    rec.rsi_14 = snap.rsi_14
    rec.macd = snap.macd
    rec.macd_signal = snap.macd_signal
    rec.atr_14 = snap.atr_14
    rec.relative_volume = snap.relative_volume
    rec.support_level = snap.support_level
    rec.resistance_level = snap.resistance_level
    rec.high_52w = snap.high_52w
    rec.low_52w = snap.low_52w
    rec.change_1d = snap.change_1d
    rec.change_5d = snap.change_5d
    rec.change_1m = snap.change_1m
    rec.change_6m = snap.change_6m


def upsert_company_data(db: Session, instrument: Instrument, info, today: DateType) -> None:
    if info is None:
        return
    # Update instrument metadata
    if info.name and not instrument.name:
        instrument.name = info.name
    if info.sector:
        instrument.sector = info.sector
    if info.industry:
        instrument.industry = info.industry
    if info.market_cap:
        instrument.market_cap = info.market_cap
    if info.currency and not instrument.currency:
        instrument.currency = info.currency

    # Fundamentals (TTM snapshot)
    fund = (
        db.query(Fundamentals)
        .filter(Fundamentals.instrument_id == instrument.id)
        .filter(Fundamentals.period == "TTM")
        .first()
    )
    if not fund:
        fund = Fundamentals(instrument_id=instrument.id, period="TTM")
        db.add(fund)
    fund.revenue = info.revenue
    fund.revenue_growth_yoy = info.revenue_growth_yoy
    fund.gross_margin = info.gross_margin
    fund.operating_margin = info.operating_margin
    fund.free_cash_flow = info.free_cash_flow
    fund.debt = info.total_debt
    fund.cash = info.total_cash
    fund.eps = info.eps
    fund.pe = info.pe
    # v3 edge-factor columns
    fund.target_mean_price = getattr(info, "target_mean_price", None)
    fund.target_high_price = getattr(info, "target_high_price", None)
    fund.target_low_price = getattr(info, "target_low_price", None)
    fund.recommendation_mean = getattr(info, "recommendation_mean", None)
    fund.num_analyst_opinions = getattr(info, "num_analyst_opinions", None)
    fund.earnings_growth_quarterly = getattr(info, "earnings_growth_quarterly", None)
    fund.earnings_growth_yoy = getattr(info, "earnings_growth_yoy", None)
    fund.revenue_growth = getattr(info, "revenue_growth", None)

    # Short data
    short = (
        db.query(ShortData)
        .filter(ShortData.instrument_id == instrument.id)
        .filter(ShortData.date == today)
        .first()
    )
    if not short:
        short = ShortData(instrument_id=instrument.id, date=today)
        db.add(short)
    short.short_interest = info.shares_short
    short.short_percent_float = info.short_percent_of_float
    short.days_to_cover = info.short_ratio
    short.float_shares = info.float_shares


def upsert_news(db: Session, instrument_id: int, news_items: list[dict]) -> list[NewsItem]:
    persisted: list[NewsItem] = []
    for it in news_items:
        # Dedupe by url+title
        existing = (
            db.query(NewsItem)
            .filter(NewsItem.instrument_id == instrument_id)
            .filter(NewsItem.title == it["title"][:500])
            .first()
        )
        if existing:
            persisted.append(existing)
            continue
        sentiment, impact, category = analyze_news(it["title"], it.get("summary", ""))
        n = NewsItem(
            instrument_id=instrument_id,
            title=it["title"][:500],
            source=it.get("publisher", "")[:128],
            url=it.get("link", "")[:1024],
            published_at=it["published_at"],
            summary=(it.get("summary") or "")[:2000],
            sentiment_score=sentiment,
            impact_score=impact,
            category=category,
        )
        db.add(n)
        persisted.append(n)
    return persisted


def recent_news_for(db: Session, instrument_id: int, days: int = 14) -> list[NewsItem]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(NewsItem)
        .filter(NewsItem.instrument_id == instrument_id)
        .filter(NewsItem.published_at >= cutoff)
        .all()
    )


def avg_volume_for(df: pd.DataFrame) -> Optional[float]:
    if df is None or df.empty or "volume" not in df.columns:
        return None
    return float(df["volume"].tail(20).mean())


def upsert_score(db: Session, instrument_id: int, fs, today: DateType, llm_text: str) -> None:
    existing = (
        db.query(ShortScore)
        .filter(ShortScore.instrument_id == instrument_id)
        .filter(ShortScore.date == today)
        .first()
    )
    if not existing:
        existing = ShortScore(instrument_id=instrument_id, date=today)
        db.add(existing)

    existing.total_score = fs.total
    existing.technical_score = fs.technical.score
    existing.news_score = fs.news.score
    existing.fundamental_score = fs.fundamental.score
    existing.macro_score = fs.macro.score
    existing.squeeze_risk_score = fs.squeeze.score
    existing.liquidity_score = fs.liquidity.score
    existing.setup_type = fs.setup_type
    existing.conviction = fs.conviction
    existing.horizon = fs.horizon
    existing.entry_price = fs.trade_plan.entry
    existing.stop_price = fs.trade_plan.stop
    existing.target_1 = fs.trade_plan.target_1
    existing.target_2 = fs.trade_plan.target_2
    existing.invalidation_reason = fs.trade_plan.invalidation
    existing.llm_explanation = llm_text
    existing.signals_json = json.dumps(fs.to_dict(), default=str)
    # v2 — flat, frontend-ready bundle. PG stores native JSON; SQLite stores TEXT.
    raw = getattr(fs, "raw_score_data", None)
    if raw is None:
        raw = {}
    # SQLite needs a JSON-serializable dict regardless; SQLAlchemy JSON
    # type handles dict serialization on both backends transparently.
    existing.raw_score_data = raw


# ---------------- Main entry points ----------------

def process_ticker(
    db: Session,
    instrument: Instrument,
    macro_events: list,
    today: DateType,
    *,
    macro_regime: Optional[dict] = None,
) -> str:
    """Process a single ticker.

    Returns one of: 'scored' (passed gates, persisted), 'rejected'
    (failed gates — still persisted so the row is visible with tier=D
    and warnings explaining why), or 'skipped' (no usable data).

    ``macro_regime`` is the result of edge_factors.detect_macro_regime()
    computed ONCE per daily run and forwarded to every ticker so the
    regime tilt can be applied as a multiplier without re-fetching the
    macro indices per ticker.
    """
    df = fetch_history(instrument.ticker, period="1y")
    if df is None or df.empty:
        return "skipped"

    snap = compute_technical_snapshot(df)
    if snap is None:
        return "skipped"

    info = fetch_info_cached(db, instrument)
    upsert_prices(db, instrument.id, df)
    upsert_technicals(db, instrument.id, snap, today)
    upsert_company_data(db, instrument, info, today)

    raw_news = fetch_news_yf(instrument.ticker)
    news_objs = upsert_news(db, instrument.id, raw_news)
    db.flush()  # garantizar IDs antes de query
    recent = recent_news_for(db, instrument.id, days=14)

    # v3 edge-factor inputs ----------------------------------------------------
    # Insider transactions: best-effort, may be None for many tickers.
    insider_df = fetch_insider_transactions(instrument.ticker)

    # Short-interest history (~last 60 days) for delta computation.
    short_cutoff = today - timedelta(days=60)
    short_rows = (
        db.query(ShortData)
        .filter(ShortData.instrument_id == instrument.id)
        .filter(ShortData.date >= short_cutoff)
        .order_by(ShortData.date.asc())
        .all()
    )

    fs = compute_final_score(
        snap,
        recent,
        info,
        macro_events,
        avg_volume=avg_volume_for(df),
        insider_df=insider_df,
        short_rows=short_rows,
        macro_regime=macro_regime,
    )

    if getattr(fs, "rejected", False):
        # Persist as a zero-score row so the universe stays observable
        # (the user can see why a name was filtered out via raw_score_data).
        upsert_score(db, instrument.id, fs, today, "")
        return "rejected"

    # Only invoke LLM for relevant scores (saves tokens)
    llm_text = explain(instrument.ticker, instrument.name or instrument.ticker, fs) if fs.total >= 55 else ""
    upsert_score(db, instrument.id, fs, today, llm_text)
    return "scored"


def run_daily_job(triggered_by: str = "manual", limit: Optional[int] = None) -> dict:
    """Run the full pipeline. `limit` caps how many tickers are processed (useful for HTTP)."""
    today = DateType.today()
    started = datetime.utcnow()
    log.info("daily job starting (triggered_by=%s, limit=%s)", triggered_by, limit)

    with session_scope() as db:
        run = JobRun(
            started_at=started,
            status="running",
            triggered_by=triggered_by,
        )
        db.add(run)
        db.flush()
        run_id = run.id

    instruments_processed = 0
    scores_generated = 0
    scores_rejected = 0
    error_msg = ""

    # v3: detect macro regime ONCE for the whole run. Lenient by design —
    # any failure returns the neutral 'mixed' regime with all tilts = 1.0,
    # which means the regime multiplier is a no-op.
    macro_regime: dict = {}
    try:
        macro_regime = detect_macro_regime()
        log.info(
            "macro regime: %s (vix=%s, slope=%s, dxy_30d=%s, spx>50d=%s, spx>200d=%s)",
            macro_regime.get("regime"),
            macro_regime.get("vix"),
            macro_regime.get("yield_curve_slope_pct"),
            macro_regime.get("dxy_change_30d_pct"),
            macro_regime.get("spx_above_50d"),
            macro_regime.get("spx_above_200d"),
        )
    except Exception as e:
        log.warning("macro regime detection failed: %s — defaulting to mixed", e)
        macro_regime = {"regime": "mixed", "tilt": {}}

    try:
        with session_scope() as db:
            ensure_instruments(db)
            macro_events = collect_macro(db)
            db.flush()

        # Process per ticker in independent transactions for resilience
        all_inst = []
        with session_scope() as db:
            q = db.query(Instrument).filter(Instrument.active == True).order_by(Instrument.id)
            if limit:
                q = q.limit(limit)
            all_inst = [(i.id, i.ticker) for i in q.all()]

        with session_scope() as db:
            macro_events = db.query(MacroEvent).filter(MacroEvent.date >= today - timedelta(days=14)).all()

        for inst_id, ticker in all_inst:
            if ticker in DELISTED_TICKERS:
                continue
            try:
                with session_scope() as db:
                    inst = db.get(Instrument, inst_id)
                    if not inst:
                        continue
                    macro_events = db.query(MacroEvent).filter(MacroEvent.date >= today - timedelta(days=14)).all()
                    result = process_ticker(db, inst, macro_events, today, macro_regime=macro_regime)
                    if result == "scored":
                        scores_generated += 1
                    elif result == "rejected":
                        scores_rejected += 1
                    instruments_processed += 1
            except Exception as e:
                log.exception("error processing %s: %s", ticker, e)
            # rate-limit gentle
            time.sleep(0.05)

    except Exception as e:
        error_msg = str(e)
        log.exception("daily job failed: %s", e)

    finished = datetime.utcnow()
    with session_scope() as db:
        run = db.get(JobRun, run_id)
        if run:
            run.finished_at = finished
            run.instruments_processed = instruments_processed
            run.scores_generated = scores_generated
            run.status = "error" if error_msg else "ok"
            run.error = error_msg

    log.info(
        "daily job finished in %.1fs: total=%d scored=%d rejected=%d skipped=%d",
        (finished - started).total_seconds(),
        instruments_processed,
        scores_generated,
        scores_rejected,
        max(0, instruments_processed - scores_generated - scores_rejected),
    )

    return {
        "run_id": run_id,
        "status": "error" if error_msg else "ok",
        "instruments_processed": instruments_processed,
        "scores_generated": scores_generated,
        "scores_rejected": scores_rejected,
        "elapsed_seconds": (finished - started).total_seconds(),
        "error": error_msg,
    }
