"""Models package — `all_models` import ensures all tables are registered."""
from app.models.instrument import Instrument
from app.models.market import PriceDaily, TechnicalIndicators
from app.models.intel import NewsItem, Fundamentals, ShortData, MacroEvent
from app.models.scoring import ShortScore, Alert, JobRun

# Used by core.database.init_db to force registration
all_models = [
    Instrument,
    PriceDaily,
    TechnicalIndicators,
    NewsItem,
    Fundamentals,
    ShortData,
    MacroEvent,
    ShortScore,
    Alert,
    JobRun,
]

__all__ = [m.__name__ for m in all_models] + ["all_models"]
