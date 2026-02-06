"""분석 API 응답 스키마"""

from typing import Dict, List

from pydantic import BaseModel


# ─── GET /correlations ──────────────────────────────


class CorrelationFactor(BaseModel):
    incident_count: float
    severity_score: float
    significant: bool


class AnalysisPeriod(BaseModel):
    start: str
    end: str


class CorrelationResponse(BaseModel):
    factors: Dict[str, CorrelationFactor]
    last_updated: str
    sample_size: int
    analysis_period: AnalysisPeriod


# ─── GET /weights ───────────────────────────────────


class WeightsResponse(BaseModel):
    category_weights: Dict[str, float]
    factor_weights: Dict[str, Dict[str, float]]
    last_updated: str
    method: str


# ─── GET /trends ────────────────────────────────────


class TrendDataPoint(BaseModel):
    day: int
    score: float


class TrendStatistics(BaseModel):
    average: float
    min: float
    max: float
    trend: str


class TrendResponse(BaseModel):
    airport_code: str
    category: str
    period: str
    data: List[TrendDataPoint]
    statistics: TrendStatistics


# ─── GET /statistics ────────────────────────────────


class StatisticsOverview(BaseModel):
    total_data_points: int
    analysis_start_date: str
    last_incident_date: str
    total_incidents: int


class CategoryStat(BaseModel):
    incidents: int
    avg_severity: float


class AirportStat(BaseModel):
    incidents: int
    risk_days: int


class StatisticsResponse(BaseModel):
    overview: StatisticsOverview
    by_category: Dict[str, CategoryStat]
    by_airport: Dict[str, AirportStat]
    updated_at: str


# ─── GET /time-series ──────────────────────────

class TimeSeriesCategories(BaseModel):
    weather: float = 0
    aviation: float = 0
    security: float = 0
    health: float = 0
    operational: float = 0
    external: float = 0


class TimeSeriesDataPoint(BaseModel):
    date: str
    total_score: float
    categories: Dict[str, float] = {}


class TimeSeriesResponse(BaseModel):
    data: List[TimeSeriesDataPoint]


# ─── GET /correlation-matrix ───────────────────

class CorrelationMatrixResponse(BaseModel):
    categories: List[str]
    matrix: List[List[float]]
