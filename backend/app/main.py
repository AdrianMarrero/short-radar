"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging, get_logger
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.api.ranking import router as ranking_router
from app.api.ticker import router as ticker_router
from app.api.admin import router as admin_router

setup_logging()
log = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting Short Radar backend (env=%s)", settings.env)
    init_db()
    if settings.env != "test":
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Short Radar API",
    description=(
        "Screening engine that ranks short-side candidates across US and "
        "European equity markets. NOT financial advice."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "name": "Short Radar API",
        "version": "0.1.0",
        "docs": "/docs",
        "disclaimer": (
            "Esta API es solo para análisis y screening. "
            "No es asesoramiento financiero. Operar en corto tiene riesgo elevado."
        ),
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(ranking_router)
app.include_router(ticker_router)
app.include_router(admin_router)
