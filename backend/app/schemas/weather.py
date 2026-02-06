"""기상 API 응답 스키마"""

from typing import List, Optional

from pydantic import BaseModel


class WeatherData(BaseModel):
    temperature: Optional[float] = None
    precipitation_1h: Optional[float] = None
    humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    wind_u: Optional[float] = None
    wind_v: Optional[float] = None
    precipitation_type: Optional[float] = None
    precipitation_type_text: Optional[str] = None
    precipitation_prob: Optional[float] = None
    sky_condition: Optional[float] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    snow_depth: Optional[float] = None
    is_strong_wind: Optional[bool] = None

    model_config = {"extra": "allow"}


class WeatherAirportData(BaseModel):
    airport_code: str
    airport_name: str
    base_datetime: Optional[str] = None
    collected_at: Optional[str] = None
    weather: WeatherData
    source: Optional[str] = None

    model_config = {"extra": "allow"}


class WeatherListResponse(BaseModel):
    collected_at: str
    count: int
    data: List[WeatherAirportData]


# ─── GET /summary ───────────────────────────────────


class StatRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    avg: Optional[float] = None


class WeatherStatistics(BaseModel):
    temperature: StatRange
    wind_speed: StatRange
    humidity: StatRange


class WeatherAlerts(BaseModel):
    strong_wind_airports: List[str]
    rainy_airports: List[str]


class WeatherSummaryAirport(BaseModel):
    code: str
    name: str
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    humidity: Optional[float] = None
    precipitation_type: Optional[str] = None


class WeatherSummaryResponse(BaseModel):
    collected_at: str
    airport_count: int
    statistics: WeatherStatistics
    alerts: WeatherAlerts
    airports: List[WeatherSummaryAirport]
