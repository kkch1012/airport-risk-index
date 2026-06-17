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
    # 데이터 신뢰도 플래그
    has_data: bool = True   # False = 유효 데이터 없음(가중치에서 제외됨)
    is_proxy: bool = False  # True = 뉴스 신호 기반 추정치(실측 아님)


class DataSourceMap(BaseModel):
    # 카테고리별 데이터 신뢰도 라벨. 엔드포인트마다 키 구성이 다를 수 있어
    # (대시보드: travel_advisory / 상세: external) 모두 선택적으로 둔다.
    weather: Optional[str] = None
    travel_advisory: Optional[str] = None
    external: Optional[str] = None
    health: Optional[str] = None
    operational: Optional[str] = None
    aviation: Optional[str] = None
    security: Optional[str] = None

    model_config = {"extra": "allow"}


class AlertSchema(BaseModel):
    airport: str
    type: str
    message: str
    severity: str
    created_at: Optional[str] = None
