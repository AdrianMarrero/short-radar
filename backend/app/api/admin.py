"""Admin / jobs / stats endpoints."""
from __future__ import annotations

from datetime import date as DateType
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.jobs.daily import run_daily_job
from app.models import Instrument, ShortScore, JobRun, MacroEvent
from app.services.backtest import backtest
from app.services.risk import size_position
from app.api.schemas import (
    StatsOut, JobRunOut, BacktestOut, MacroEventOut,
    PositionSizeIn, PositionSizeOut, WeightsIn,
)

router = APIRouter(prefix="/api", tags=["admin"])
settings = get_settings()


def require_admin(x_admin_token: str | None = Header(default=None)):
    if not settings.admin_token:
        return  # admin desactivado
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="invalid admin token")


# -------- Jobs --------

@router.post("/jobs/run-daily")
def trigger_daily_job(
    background: BackgroundTasks,
    limit: Optional[int] = Query(None, description="Limit number of tickers (for testing)"),
    _admin = Depends(require_admin),
):
    """Trigger the full daily pipeline asynchronously. Returns immediately."""
    background.add_task(run_daily_job, "manual", limit)
    return {"status": "started", "limit": limit}


@router.post("/jobs/run-daily-batch")
def run_daily_batch_sync(
    limit: int = Query(40, ge=1, le=200),
    _admin = Depends(require_admin),
):
    """Synchronous batched run (used by the cron job)."""
    return run_daily_job(triggered_by="cron", limit=limit)


@router.get("/jobs/runs", response_model=list[JobRunOut])
def list_job_runs(db: Session = Depends(get_db), limit: int = 20):
    return (
        db.query(JobRun)
        .order_by(JobRun.started_at.desc())
        .limit(limit)
        .all()
    )


# -------- Stats --------

@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    total_instruments = db.query(func.count(Instrument.id)).scalar() or 0
    today = DateType.today()
    total_today = db.query(func.count(ShortScore.id)).filter(ShortScore.date == today).scalar() or 0
    avg_score = db.query(func.avg(ShortScore.total_score)).filter(ShortScore.date == today).scalar() or 0.0
    last_run = db.query(JobRun).order_by(JobRun.started_at.desc()).first()
    setup_dist_rows = (
        db.query(ShortScore.setup_type, func.count(ShortScore.id))
        .filter(ShortScore.date == today)
        .group_by(ShortScore.setup_type)
        .all()
    )
    setup_dist = {k or "unknown": int(c) for k, c in setup_dist_rows}

    return StatsOut(
        total_instruments=int(total_instruments),
        total_scores_today=int(total_today),
        last_job_run=JobRunOut.model_validate(last_run) if last_run else None,
        avg_score=float(round(avg_score, 2)),
        top_setup_distribution=setup_dist,
    )


# -------- Macro --------

@router.get("/macro", response_model=list[MacroEventOut])
def get_macro(db: Session = Depends(get_db), limit: int = 20):
    return (
        db.query(MacroEvent)
        .order_by(MacroEvent.date.desc(), MacroEvent.impact_score.desc())
        .limit(limit)
        .all()
    )


# -------- Backtest --------

@router.get("/backtest", response_model=BacktestOut)
def run_backtest(
    db: Session = Depends(get_db),
    min_score: float = 65,
    hold_days: int = 10,
):
    res = backtest(db, min_score=min_score, hold_days=hold_days)
    return BacktestOut(
        n_trades=res.n_trades,
        win_rate_pct=res.win_rate_pct,
        avg_return_pct=res.avg_return_pct,
        avg_hold_days=res.avg_hold_days,
        by_setup=res.by_setup,
    )


# -------- Position sizing --------

@router.post("/risk/position-size", response_model=PositionSizeOut)
def position_size(payload: PositionSizeIn):
    res = size_position(
        capital=payload.capital,
        risk_pct=payload.risk_pct,
        entry=payload.entry,
        stop=payload.stop,
        target=payload.target,
    )
    return PositionSizeOut(
        shares=res.shares,
        risk_per_share=res.risk_per_share,
        max_loss=res.max_loss,
        max_gain=res.max_gain,
        risk_reward=res.risk_reward,
        warning=res.warning,
    )


# -------- Weights (read-only for now) --------

@router.get("/config/weights", response_model=WeightsIn)
def get_weights():
    return WeightsIn(
        technical=settings.weight_technical,
        news=settings.weight_news,
        fundamental=settings.weight_fundamental,
        macro=settings.weight_macro,
        liquidity=settings.weight_liquidity,
    )
