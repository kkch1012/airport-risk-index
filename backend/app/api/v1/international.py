"""
해외 데이터 API 엔드포인트

- 해외 항공사고/준사고 목록
- 해외 공항 기상 현황
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/incidents")
async def get_international_incidents(
    country_code: Optional[str] = Query(None, description="국가 코드 (JP, CN 등)"),
    severity: Optional[str] = Query(None, description="심각도 필터 (fatal/serious/minor)"),
    limit: int = Query(20, ge=1, le=100),
):
    """해외 항공사고/준사고 목록 조회"""
    from app.collectors.international_aviation import InternationalAviationCollector

    async with InternationalAviationCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        return {"incidents": [], "total": 0, "source": "unavailable"}

    incidents = result["data"]

    # 필터링
    if country_code:
        incidents = [i for i in incidents if i.get("country_code") == country_code.upper()]
    if severity:
        incidents = [i for i in incidents if i.get("severity") == severity.lower()]

    # 정렬 (최신순) + 제한
    incidents.sort(key=lambda x: x.get("incident_date", ""), reverse=True)
    incidents = incidents[:limit]

    return {
        "incidents": incidents,
        "total": len(incidents),
        "source": "Aviation Safety Network",
    }


@router.get("/weather")
async def get_international_weather(
    country_code: Optional[str] = Query(None, description="국가 코드"),
):
    """해외 공항 기상 현황 조회"""
    from app.collectors.international_weather import InternationalWeatherCollector

    async with InternationalWeatherCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        return {"weather": [], "total": 0, "source": "unavailable"}

    weather_data = result["data"]

    if country_code:
        weather_data = [w for w in weather_data if w.get("country_code") == country_code.upper()]

    # 위험도 높은 순 정렬
    weather_data.sort(key=lambda x: x.get("risk_score", 0), reverse=True)

    return {
        "weather": weather_data,
        "total": len(weather_data),
        "source": "Aviation Weather (METAR)",
    }


@router.get("/summary")
async def get_international_summary():
    """해외 데이터 종합 요약"""
    from app.collectors.international_aviation import InternationalAviationCollector
    from app.collectors.international_weather import InternationalWeatherCollector

    # 병렬 수집
    import asyncio
    aviation_task = asyncio.create_task(_collect_aviation())
    weather_task = asyncio.create_task(_collect_weather())

    aviation_data = await aviation_task
    weather_data = await weather_task

    # 고위험 항목
    high_risk_incidents = [i for i in aviation_data if i.get("risk_score", 0) >= 50]
    high_risk_weather = [w for w in weather_data if w.get("risk_score", 0) >= 40]

    return {
        "incidents": {
            "total": len(aviation_data),
            "high_risk": len(high_risk_incidents),
            "recent": aviation_data[:5],
        },
        "weather": {
            "total": len(weather_data),
            "high_risk": len(high_risk_weather),
            "alerts": high_risk_weather[:5],
        },
    }


async def _collect_aviation():
    from app.collectors.international_aviation import InternationalAviationCollector
    async with InternationalAviationCollector() as c:
        result = await c.run()
    return result.get("data", []) if result["status"] == "success" else []


async def _collect_weather():
    from app.collectors.international_weather import InternationalWeatherCollector
    async with InternationalWeatherCollector() as c:
        result = await c.run()
    return result.get("data", []) if result["status"] == "success" else []
