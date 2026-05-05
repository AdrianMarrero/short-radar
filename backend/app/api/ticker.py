"""Per-ticker detail endpoint and other instrument-level endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.ranking import _sanitize_floats, _row_to_score_out
from app.core.database import get_db
from app.models import (
    Instrument, ShortScore, TechnicalIndicators, Fundamentals,
    ShortData, NewsItem, PriceDaily,
)
from app.api.schemas import (
    TickerDetailOut, InstrumentOut, TechnicalsOut,
    FundamentalsOut, ShortDataOut, NewsItemOut, PriceOut,
)

router = APIRouter(prefix="/api/ticker", tags=["ticker"])


@router.get("/{ticker}", response_model=TickerDetailOut)
def get_ticker_detail(ticker: str, db: Session = Depends(get_db)):
    inst = db.query(Instrument).filter(Instrument.ticker == ticker.upper()).first()
    if not inst:
        # Try as-is in case it's a European ticker (suffix-sensitive)
        inst = db.query(Instrument).filter(Instrument.ticker == ticker).first()
    if not inst:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")

    score = (
        db.query(ShortScore)
        .filter(ShortScore.instrument_id == inst.id)
        .order_by(ShortScore.date.desc())
        .first()
    )
    tech = (
        db.query(TechnicalIndicators)
        .filter(TechnicalIndicators.instrument_id == inst.id)
        .order_by(TechnicalIndicators.date.desc())
        .first()
    )
    fund = (
        db.query(Fundamentals)
        .filter(Fundamentals.instrument_id == inst.id)
        .filter(Fundamentals.period == "TTM")
        .first()
    )
    short = (
        db.query(ShortData)
        .filter(ShortData.instrument_id == inst.id)
        .order_by(ShortData.date.desc())
        .first()
    )
    prices = (
        db.query(PriceDaily)
        .filter(PriceDaily.instrument_id == inst.id)
        .order_by(PriceDaily.date.desc())
        .limit(60)
        .all()
    )
    prices = list(reversed(prices))

    cutoff = datetime.utcnow() - timedelta(days=21)
    news = (
        db.query(NewsItem)
        .filter(NewsItem.instrument_id == inst.id)
        .filter(NewsItem.published_at >= cutoff)
        .order_by(NewsItem.published_at.desc())
        .limit(20)
        .all()
    )

    last_close = float(prices[-1].close) if prices and prices[-1].close else None

    score_out = None
    if score:
        # Reuse the ranking hydrator so v2 fields + probabilistic layer
        # are populated consistently (single source of truth).
        score_out = _row_to_score_out(score, inst, tech)
        score_out.last_close = last_close

    detail = TickerDetailOut(
        instrument=InstrumentOut.model_validate(inst),
        score=score_out,
        technicals=TechnicalsOut.model_validate(tech) if tech else None,
        fundamentals=FundamentalsOut.model_validate(fund) if fund else None,
        short_data=ShortDataOut.model_validate(short) if short else None,
        recent_prices=[PriceOut.model_validate(p) for p in prices],
        recent_news=[NewsItemOut.model_validate(n) for n in news],
        explanation=score.llm_explanation if score else "",
    )
    # Sanitize NaN/Inf at the response boundary — yfinance returns NaN
    # for some fields (esp. European tickers' fundamentals) which
    # crashes stdlib json.dumps with "Out of range float values".
    return JSONResponse(content=_sanitize_floats(detail.model_dump(mode="json")))
