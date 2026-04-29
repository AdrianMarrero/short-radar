"""Per-ticker detail endpoint and other instrument-level endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import (
    Instrument, ShortScore, TechnicalIndicators, Fundamentals,
    ShortData, NewsItem, PriceDaily,
)
from app.api.schemas import (
    TickerDetailOut, InstrumentOut, ScoreOut, TechnicalsOut,
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
        score_out = ScoreOut(
            instrument_id=inst.id,
            ticker=inst.ticker,
            name=inst.name or inst.ticker,
            exchange=inst.exchange,
            sector=inst.sector or "",
            last_close=last_close,
            change_1d=tech.change_1d if tech else None,
            change_5d=tech.change_5d if tech else None,
            change_1m=tech.change_1m if tech else None,
            total_score=score.total_score,
            technical_score=score.technical_score,
            news_score=score.news_score,
            fundamental_score=score.fundamental_score,
            macro_score=score.macro_score,
            squeeze_risk_score=score.squeeze_risk_score,
            liquidity_score=score.liquidity_score,
            setup_type=score.setup_type,
            conviction=score.conviction,
            horizon=score.horizon,
            entry_price=score.entry_price,
            stop_price=score.stop_price,
            target_1=score.target_1,
            target_2=score.target_2,
            invalidation_reason=score.invalidation_reason or "",
        )

    return TickerDetailOut(
        instrument=InstrumentOut.model_validate(inst),
        score=score_out,
        technicals=TechnicalsOut.model_validate(tech) if tech else None,
        fundamentals=FundamentalsOut.model_validate(fund) if fund else None,
        short_data=ShortDataOut.model_validate(short) if short else None,
        recent_prices=[PriceOut.model_validate(p) for p in prices],
        recent_news=[NewsItemOut.model_validate(n) for n in news],
        explanation=score.llm_explanation if score else "",
    )
