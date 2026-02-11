"""예측 API 응답 스키마"""

from typing import Dict, List, Optional

from pydantic import BaseModel


class ForecastPointSchema(BaseModel):
    date: str
    value: float
    lower_ci: float
    upper_ci: float


class ForecastMetrics(BaseModel):
    mae: float
    rmse: float
    method: str
    data_points_used: int


class AirportForecastResponse(BaseModel):
    airport_code: str
    category: str
    horizon: int
    last_observed: Optional[ForecastPointSchema] = None
    predictions: List[ForecastPointSchema]
    metrics: ForecastMetrics
