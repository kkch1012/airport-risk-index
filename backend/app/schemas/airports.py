"""공항 API 응답 스키마"""

from typing import List

from pydantic import BaseModel


class AirportDetail(BaseModel):
    code: str
    name: str
    region: str
    latitude: float
    longitude: float


class AirportListResponse(BaseModel):
    total: int
    airports: List[AirportDetail]


class RegionListResponse(BaseModel):
    regions: List[str]
