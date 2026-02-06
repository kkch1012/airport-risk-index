"""
Celery 태스크용 유틸리티
"""

import asyncio
import logging
from typing import Any, Coroutine, Dict, List, Tuple

from app.collectors.weather import WeatherCollector
from app.collectors.travel_advisory import TravelAdvisoryCollector
from app.collectors.health_risk import HealthRiskCollector
from app.collectors.flight_status import FlightStatusCollector
from app.collectors.aviation_safety import AviationSafetyCollector

logger = logging.getLogger(__name__)


def run_async(coro: Coroutine) -> Any:
    """Celery sync 태스크에서 async 코루틴을 실행하는 브릿지"""
    return asyncio.run(coro)


async def collect_weather() -> Dict[str, Any]:
    """기상 데이터를 공항 코드별로 매핑하여 반환"""
    async with WeatherCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        logger.warning("Weather collection failed: %s", result.get("error"))
        return {}

    weather_map = {}
    for data in result["data"]:
        weather_map[data["airport_code"]] = data["weather"]
    return weather_map


async def collect_travel_advisory() -> Tuple[List[Dict], bool]:
    """여행경보 데이터 수집"""
    async with TravelAdvisoryCollector() as collector:
        result = await collector.run()
    if result["status"] != "success":
        logger.warning("Travel advisory collection failed: %s", result.get("error"))
        return [], False
    return result["data"], bool(collector.api_key)


async def collect_health() -> Tuple[List[Dict], bool]:
    """보건위험 데이터 수집"""
    async with HealthRiskCollector() as collector:
        result = await collector.run()
    if result["status"] != "success":
        logger.warning("Health risk collection failed: %s", result.get("error"))
        return [], False
    return result["data"], bool(collector.api_key)


async def collect_operational() -> Tuple[List[Dict], bool]:
    """운항정보 데이터 수집"""
    async with FlightStatusCollector() as collector:
        result = await collector.run()
    if result["status"] != "success":
        logger.warning("Flight status collection failed: %s", result.get("error"))
        return [], False
    return result["data"], bool(collector.api_key)


async def collect_aviation() -> Tuple[List[Dict], bool]:
    """항공안전 데이터 수집"""
    async with AviationSafetyCollector() as collector:
        result = await collector.run()
    if result["status"] != "success":
        logger.warning("Aviation safety collection failed: %s", result.get("error"))
        return [], False
    return result["data"], collector.can_crawl
