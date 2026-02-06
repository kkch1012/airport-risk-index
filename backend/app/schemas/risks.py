"""위험지수 API 응답 스키마"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.schemas.common import (
    AirportBase,
    AlertSchema,
    CategoryScoreSchema,
    DataSourceMap,
)


# ─── GET /dashboard ─────────────────────────────────


class DashboardSummary(BaseModel):
    total_airports: int
    high_risk_count: int
    average_score: float
    updated_at: str


class DashboardAirport(BaseModel):
    code: str
    name: str
    score: float
    level: str
    weather_score: float
    external_score: float
    health_score: float
    operational_score: float
    aviation_score: float


class DashboardResponse(BaseModel):
    summary: DashboardSummary
    airports: List[DashboardAirport]
    alerts: List[AlertSchema]
    data_sources: DataSourceMap


# ─── GET /airports/{code} ──────────────────────────


class AirportRiskResponse(BaseModel):
    airport: AirportBase
    date: str
    total_score: float
    risk_level: str
    categories: Dict[str, CategoryScoreSchema]
    updated_at: str
    data_source: DataSourceMap


# ─── GET /airports/{code}/history ──────────────────


class HistoryEntry(BaseModel):
    date: str
    total_score: float
    risk_level: str


class RiskHistoryResponse(BaseModel):
    airport_code: str
    start_date: str
    end_date: str
    history: List[HistoryEntry]


# ─── GET /comparison ───────────────────────────────


class ComparisonAirport(BaseModel):
    code: str
    name: str
    total_score: float
    categories: Dict[str, float]


class ComparisonResponse(BaseModel):
    date: str
    comparison: List[ComparisonAirport]


# ─── GET /travel-advisory ─────────────────────────


class TravelAdvisoryLevelDistribution(BaseModel):
    no_warning: int
    caution: int
    restriction: int
    advisory: int
    prohibition: int


class TravelAdvisoryHighRisk(BaseModel):
    code: str
    name: str
    level: int
    alarm_name: str


class TravelAdvisorySummary(BaseModel):
    total_countries: int
    level_distribution: TravelAdvisoryLevelDistribution
    high_risk_countries: List[TravelAdvisoryHighRisk]
    average_risk_score: float


class TravelAdvisoryCountry(BaseModel):
    country_code: str
    country_name: str
    country_name_eng: Optional[str] = ""
    continent_name: Optional[str] = ""
    alarm_level: int
    alarm_name: str
    alarm_color: str
    risk_score: float
    is_partial_warning: bool
    region_type: Optional[str] = ""
    remark: Optional[str] = ""
    written_date: Optional[str] = ""
    collected_at: str
    source: str


class TravelAdvisoryResponse(BaseModel):
    updated_at: str
    data_source: str
    summary: TravelAdvisorySummary
    countries: List[TravelAdvisoryCountry]


# ─── GET /health-risk ─────────────────────────────


class HealthRiskHighRegion(BaseModel):
    country: str
    country_code: str
    disease: str
    risk_score: float


class HealthRiskSummary(BaseModel):
    total_quarantine_regions: int
    disease_distribution: Dict[str, int]
    high_risk_regions: List[HealthRiskHighRegion]
    average_risk_score: float
    countries_with_quarantine: int
    country_risk_summary: Dict[str, float]


class QuarantineRegion(BaseModel):
    country_code: str
    country_name: str
    disease_code: str
    disease_name: str
    designation_date: Optional[str] = ""
    release_date: Optional[str] = ""
    is_active: bool
    risk_score: float
    risk_group: Optional[str] = ""
    collected_at: str
    source: str


class HealthRiskResponse(BaseModel):
    updated_at: str
    data_source: str
    summary: HealthRiskSummary
    quarantine_regions: List[QuarantineRegion]


# ─── GET /health-risk/airports/{code} ─────────────


class AffectedRouteDisease(BaseModel):
    name: str
    risk_score: float


class AffectedRoute(BaseModel):
    country_code: str
    country_name: str
    risk_score: float
    diseases: List[AffectedRouteDisease]


class AirportHealthRiskResponse(BaseModel):
    updated_at: str
    data_source: str
    airport: AirportBase
    airport_code: str
    health_risk_score: float
    risk_level: str
    affected_routes: List[AffectedRoute]
    total_routes_checked: Optional[int] = None
    routes_with_quarantine: Optional[int] = None
    message: Optional[str] = None


# ─── GET /flight-status ───────────────────────────


class FlightStatusHighRiskAirport(BaseModel):
    airport_code: str
    airport_name: str
    delay_rate: float
    cancellation_rate: float
    operational_score: float


class FlightStatusSummary(BaseModel):
    total_airports: int
    total_flights: int
    average_delay_rate: float
    average_cancellation_rate: float
    high_risk_airports: List[FlightStatusHighRiskAirport]


class FlightStatusAirport(BaseModel):
    airport_code: str
    airport_name: str
    date: Optional[str] = None
    total_flights: int
    departure_count: Optional[int] = None
    arrival_count: Optional[int] = None
    delayed_flights: int
    cancelled_flights: int
    delay_rate: float
    cancellation_rate: float
    average_delay_minutes: float
    congestion_level: Optional[str] = None
    operational_score: Optional[float] = None
    collected_at: str
    source: Optional[str] = None

    model_config = {"extra": "allow"}


class FlightStatusResponse(BaseModel):
    updated_at: str
    data_source: str
    summary: FlightStatusSummary
    airports: List[FlightStatusAirport]


# ─── GET /flight-status/airports/{code} ───────────


class AirportFlightStatusResponse(BaseModel):
    updated_at: str
    data_source: str
    airport: AirportBase
    airport_code: Optional[str] = None
    airport_name: Optional[str] = None
    date: Optional[str] = None
    total_flights: Optional[int] = None
    departure_count: Optional[int] = None
    arrival_count: Optional[int] = None
    delayed_flights: Optional[int] = None
    cancelled_flights: Optional[int] = None
    delay_rate: Optional[float] = None
    cancellation_rate: Optional[float] = None
    average_delay_minutes: Optional[float] = None
    congestion_level: Optional[str] = None
    operational_score: Optional[float] = None
    collected_at: Optional[str] = None
    source: Optional[str] = None
    message: Optional[str] = None

    model_config = {"extra": "allow"}
