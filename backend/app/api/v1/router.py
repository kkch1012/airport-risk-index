"""
API v1 라우터 통합
"""

from fastapi import APIRouter

from app.api.v1 import airports, risks, analytics, weather

api_router = APIRouter()

# 서브 라우터 등록
api_router.include_router(airports.router, prefix="/airports", tags=["airports"])
api_router.include_router(risks.router, prefix="/risks", tags=["risks"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(weather.router, prefix="/weather", tags=["weather"])
