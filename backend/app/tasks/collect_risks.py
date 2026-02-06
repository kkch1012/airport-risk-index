"""
위험지수 데이터 수집 및 계산 Celery 태스크
"""

import logging

from app.core.celery_app import celery_app
from app.core.constants import AIRPORT_NAMES
from app.services.risk_calculator import RiskCalculator
from app.services.risk_history_service import RiskHistoryService
from app.core.database import AsyncSessionLocal
from app.tasks.utils import (
    run_async,
    collect_weather,
    collect_travel_advisory,
    collect_health,
    collect_operational,
    collect_aviation,
)

logger = logging.getLogger(__name__)


async def _collect_and_calculate():
    """전체 수집 → 계산 → DB 저장 파이프라인 (async)"""
    calculator = RiskCalculator()

    # 1. 데이터 수집
    logger.info("Starting data collection for all sources")
    weather_map = await collect_weather()
    travel_advisory_data, _ = await collect_travel_advisory()
    health_data, _ = await collect_health()
    operational_data, _ = await collect_operational()
    aviation_data, _ = await collect_aviation()

    logger.info(
        "Collection complete — weather: %d airports, advisory: %d, health: %d, "
        "operational: %d, aviation: %d",
        len(weather_map),
        len(travel_advisory_data),
        len(health_data),
        len(operational_data),
        len(aviation_data),
    )

    # 2. 위험지수 계산
    risk_results = []
    for code, name in AIRPORT_NAMES.items():
        risk_result = calculator.calculate_total_risk(
            airport_code=code,
            airport_name=name,
            weather_data=weather_map.get(code),
            travel_advisory_data=travel_advisory_data,
            health_data=health_data,
            operational_data=operational_data,
            aviation_data=aviation_data,
        )
        risk_results.append(risk_result)

    high_risk = [r for r in risk_results if r.risk_level in ("HIGH", "CRITICAL")]
    logger.info(
        "Calculated %d airport risks — %d HIGH/CRITICAL",
        len(risk_results),
        len(high_risk),
    )

    # 3. DB 저장
    async with AsyncSessionLocal() as session:
        service = RiskHistoryService(session)
        saved = await service.save_batch(risk_results)

    logger.info("Saved %d/%d risk assessments to DB", saved, len(risk_results))
    return {
        "airports": len(risk_results),
        "saved": saved,
        "high_risk": len(high_risk),
    }


async def _collect_weather_only():
    """기상 데이터 단독 수집 (async)"""
    weather_map = await collect_weather()
    logger.info("Weather collection complete — %d airports", len(weather_map))
    return {"airports_collected": len(weather_map)}


async def _collect_advisory_only():
    """여행경보 데이터 단독 수집 (async)"""
    data, is_real = await collect_travel_advisory()
    logger.info(
        "Travel advisory collection complete — %d countries (real=%s)",
        len(data),
        is_real,
    )
    return {"countries_collected": len(data), "is_real_data": is_real}


@celery_app.task(
    name="app.tasks.collect_risks.collect_and_calculate_all_risks",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def collect_and_calculate_all_risks(self):
    """전체 데이터 수집 + 위험지수 계산 + DB 저장"""
    logger.info("[Task] collect_and_calculate_all_risks started")
    try:
        result = run_async(_collect_and_calculate())
        logger.info("[Task] collect_and_calculate_all_risks completed: %s", result)
        return result
    except Exception as exc:
        logger.exception("[Task] collect_and_calculate_all_risks failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.collect_risks.collect_weather_data",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def collect_weather_data(self):
    """기상 데이터 단독 수집"""
    logger.info("[Task] collect_weather_data started")
    try:
        result = run_async(_collect_weather_only())
        logger.info("[Task] collect_weather_data completed: %s", result)
        return result
    except Exception as exc:
        logger.exception("[Task] collect_weather_data failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.collect_risks.collect_advisory_data",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def collect_advisory_data(self):
    """여행경보 데이터 단독 수집"""
    logger.info("[Task] collect_advisory_data started")
    try:
        result = run_async(_collect_advisory_only())
        logger.info("[Task] collect_advisory_data completed: %s", result)
        return result
    except Exception as exc:
        logger.exception("[Task] collect_advisory_data failed")
        raise self.retry(exc=exc)
