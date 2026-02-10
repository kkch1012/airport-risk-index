"""공유 enum 및 기본 스키마"""

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel


# ─── Enums ──────────────────────────────────────────


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    WEATHER = "WEATHER"
    SECURITY = "SECURITY"
    HEALTH = "HEALTH"
    OPERATIONAL = "OPERATIONAL"


class AlertSeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class CategoryCode(str, Enum):
    WEATHER = "weather"
    AVIATION = "aviation"
    SECURITY = "security"
    HEALTH = "health"
    OPERATIONAL = "operational"
    EXTERNAL = "external"


class TrendPeriod(str, Enum):
    ONE_WEEK = "1W"
    ONE_MONTH = "1M"
    THREE_MONTHS = "3M"
    SIX_MONTHS = "6M"
    ONE_YEAR = "1Y"


# ─── Base Schemas ───────────────────────────────────


class AirportBase(BaseModel):
    code: str
    name: str


class CategoryScoreSchema(BaseModel):
    name: str
    score: float
    level: str
    factors: Dict[str, float]


class DataSourceMap(BaseModel):
    weather: str
    travel_advisory: str
    health: str
    operational: str
    aviation: str
    security: Optional[str] = None

    model_config = {"extra": "allow"}


class AlertSchema(BaseModel):
    airport: str
    type: str
    message: str
    severity: str
    created_at: Optional[str] = None