"""
Pydantic schemas for API request/response validation.

Organized by domain:
- common: Shared enums and base models
- risks: Risk assessment endpoints
- airports: Airport information endpoints
- weather: Weather data endpoints
- analytics: Analysis and statistics endpoints
"""

from app.schemas.common import (
    RiskLevel,
    AlertType,
    AlertSeverity,
    CategoryCode,
    TrendPeriod,
    AirportBase,
    CategoryScoreSchema,
    DataSourceMap,
    AlertSchema,
)

__all__ = [
    "RiskLevel",
    "AlertType",
    "AlertSeverity",
    "CategoryCode",
    "TrendPeriod",
    "AirportBase",
    "CategoryScoreSchema",
    "DataSourceMap",
    "AlertSchema",
]
