"""
위험지수 데이터 수집 및 계산 Celery 태스크
"""

import logging
import time

from app.core.celery_app import celery_app
from app.core.metrics import (
    risk_score_current,
    risk_calculation_duration,
    collector_runs_total,
    collector_duration,
    celery_tasks_total,
    celery_task_duration,
    alerts_sent_total,
)
from app.core.constants import AIRPORT_NAMES
from app.services.risk_calculator import RiskCalculator
from app.services.risk_history_service import RiskHistoryService
from app.services.alert_service import AlertService
from app.services.forecast_service import ForecastService
from app.services.weight_service import WeightService
from app.core.database import AsyncSessionLocal
from app.tasks.utils import (
    run_async,
    collect_weather,
    collect_travel_advisory,
    collect_health,
    collect_operational,
    collect_aviation,
    collect_security,
    collect_international_weather,
    collect_international_aviation,
)

logger = logging.getLogger(__name__)


async def _collect_and_calculate():
    """전체 수집 → 계산 → DB 저장 파이프라인 (async)"""
    # 동적 가중치 로드
    try:
        async with AsyncSessionLocal() as session:
            weight_service = WeightService(session)
            active_weights = await weight_service.get_active_category_weights()
    except Exception:
        logger.warning("Failed to load dynamic weights, using defaults")
        active_weights = None

    calculator = RiskCalculator(custom_weights=active_weights)

    # 1. 데이터 수집 (메트릭 계측 포함)
    logger.info("Starting data collection for all sources")

    async def _timed_collect(name, coro):
        """수집기 실행 시간/성공 여부를 Prometheus 메트릭으로 기록"""
        start = time.perf_counter()
        try:
            result = await coro
            elapsed = time.perf_counter() - start
            if collector_duration is not None:
                collector_duration.labels(collector=name).observe(elapsed)
            if collector_runs_total is not None:
                collector_runs_total.labels(collector=name, status="success").inc()
            return result
        except Exception:
            elapsed = time.perf_counter() - start
            if collector_duration is not None:
                collector_duration.labels(collector=name).observe(elapsed)
            if collector_runs_total is not None:
                collector_runs_total.labels(collector=name, status="failure").inc()
            raise

    weather_map = await _timed_collect("weather", collect_weather())
    travel_advisory_data, _ = await _timed_collect("travel_advisory", collect_travel_advisory())
    health_data, _ = await _timed_collect("health", collect_health())
    operational_data, _ = await _timed_collect("operational", collect_operational())
    aviation_data, _ = await _timed_collect("aviation", collect_aviation())
    security_data, _ = await _timed_collect("security", collect_security())
    intl_weather_data = await _timed_collect("intl_weather", collect_international_weather())
    intl_aviation_data = await _timed_collect("intl_aviation", collect_international_aviation())

    logger.info(
        "Collection complete — weather: %d airports, advisory: %d, health: %d, "
        "operational: %d, aviation: %d, security: %d, intl_weather: %d, intl_aviation: %d",
        len(weather_map),
        len(travel_advisory_data),
        len(health_data),
        len(operational_data),
        len(aviation_data),
        len(security_data),
        len(intl_weather_data),
        len(intl_aviation_data),
    )

    # 2. 위험지수 계산 (소요시간 메트릭)
    calc_start = time.perf_counter()
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
            international_weather_data=intl_weather_data,
            international_aviation_data=intl_aviation_data,
            security_data=security_data,
        )
        risk_results.append(risk_result)

    calc_elapsed = time.perf_counter() - calc_start
    if risk_calculation_duration is not None:
        risk_calculation_duration.observe(calc_elapsed)

    # 공항별 현재 위험지수 Gauge 업데이트
    if risk_score_current is not None:
        for r in risk_results:
            risk_score_current.labels(airport_code=r.airport_code).set(r.total_score)

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

    # 4. HIGH/CRITICAL 알림 발송
    notified = 0
    if high_risk:
        try:
            alert_service = AlertService()
            notified = alert_service.check_and_notify(risk_results)
            if alerts_sent_total is not None and notified > 0:
                for r in high_risk:
                    alerts_sent_total.labels(severity=r.risk_level).inc()
        except Exception:
            logger.exception("Alert notification failed (non-fatal)")

    # 5. 캐시 무효화
    try:
        from app.core.cache import invalidate_cache
        invalidate_cache("dashboard")
        invalidate_cache("airport_risk")
        invalidate_cache("trends")
    except Exception:
        logger.debug("Cache invalidation failed (non-fatal)")

    # 6. WebSocket 실시간 업데이트 (Redis Pub/Sub)
    try:
        from app.core.redis_pubsub import publish_risk_update_sync
        from datetime import datetime

        ws_data = {
            "type": "risk_update",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "airports": [
                    {
                        "airport_code": r.airport_code,
                        "airport_name": r.airport_name,
                        "total_score": r.total_score,
                        "risk_level": r.risk_level,
                    }
                    for r in risk_results
                ],
                "summary": {
                    "total_airports": len(risk_results),
                    "high_risk_count": len(high_risk),
                    "average_score": round(
                        sum(r.total_score for r in risk_results) / len(risk_results), 2
                    ) if risk_results else 0,
                },
            },
        }
        publish_risk_update_sync(ws_data)
    except Exception:
        logger.debug("WebSocket publish failed (non-fatal)")

    return {
        "airports": len(risk_results),
        "saved": saved,
        "high_risk": len(high_risk),
        "notified": notified,
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


async def _recalculate_weights():
    """가중치 재산출 파이프라인 (async)"""
    async with AsyncSessionLocal() as session:
        service = WeightService(session)
        result = await service.calculate_and_save_weights(
            method="ensemble", lookback_days=365
        )

    if result:
        return {
            "status": "success",
            "method": result.method,
            "sample_size": result.sample_size,
            "weights": result.category_weights,
        }
    return {"status": "skipped", "reason": "insufficient_data"}


async def _send_daily_report():
    """일일 리포트 생성 + 발송 (async)"""
    try:
        async with AsyncSessionLocal() as session:
            weight_service = WeightService(session)
            active_weights = await weight_service.get_active_category_weights()
    except Exception:
        active_weights = None

    calculator = RiskCalculator(custom_weights=active_weights)

    weather_map = await collect_weather()
    travel_advisory_data, _ = await collect_travel_advisory()
    health_data, _ = await collect_health()
    operational_data, _ = await collect_operational()
    aviation_data, _ = await collect_aviation()
    security_data, _ = await collect_security()

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
            security_data=security_data,
        )
        risk_results.append(risk_result)

    alert_service = AlertService()
    sent = alert_service.send_daily_report(risk_results)
    logger.info("Daily report sent: %s (%d airports)", sent, len(risk_results))
    return {"sent": sent, "airports": len(risk_results)}


@celery_app.task(
    name="app.tasks.collect_risks.collect_and_calculate_all_risks",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def collect_and_calculate_all_risks(self):
    """전체 데이터 수집 + 위험지수 계산 + DB 저장"""
    task_name = "collect_and_calculate"
    logger.info("[Task] collect_and_calculate_all_risks started")
    start = time.perf_counter()
    try:
        result = run_async(_collect_and_calculate())
        elapsed = time.perf_counter() - start
        if celery_task_duration is not None:
            celery_task_duration.labels(task_name=task_name).observe(elapsed)
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="success").inc()
        logger.info("[Task] collect_and_calculate_all_risks completed: %s", result)
        return result
    except Exception as exc:
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="failure").inc()
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
    task_name = "collect_weather"
    logger.info("[Task] collect_weather_data started")
    start = time.perf_counter()
    try:
        result = run_async(_collect_weather_only())
        elapsed = time.perf_counter() - start
        if celery_task_duration is not None:
            celery_task_duration.labels(task_name=task_name).observe(elapsed)
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="success").inc()
        logger.info("[Task] collect_weather_data completed: %s", result)
        return result
    except Exception as exc:
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="failure").inc()
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
    task_name = "collect_advisory"
    logger.info("[Task] collect_advisory_data started")
    start = time.perf_counter()
    try:
        result = run_async(_collect_advisory_only())
        elapsed = time.perf_counter() - start
        if celery_task_duration is not None:
            celery_task_duration.labels(task_name=task_name).observe(elapsed)
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="success").inc()
        logger.info("[Task] collect_advisory_data completed: %s", result)
        return result
    except Exception as exc:
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="failure").inc()
        logger.exception("[Task] collect_advisory_data failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.collect_risks.send_daily_report",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def send_daily_report(self):
    """일일 리포트 발송"""
    task_name = "daily_report"
    logger.info("[Task] send_daily_report started")
    start = time.perf_counter()
    try:
        result = run_async(_send_daily_report())
        elapsed = time.perf_counter() - start
        if celery_task_duration is not None:
            celery_task_duration.labels(task_name=task_name).observe(elapsed)
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="success").inc()
        logger.info("[Task] send_daily_report completed: %s", result)
        return result
    except Exception as exc:
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="failure").inc()
        logger.exception("[Task] send_daily_report failed")
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.collect_risks.recalculate_weights",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def recalculate_weights(self):
    """주간 가중치 재산출"""
    task_name = "recalculate_weights"
    logger.info("[Task] recalculate_weights started")
    start = time.perf_counter()
    try:
        result = run_async(_recalculate_weights())
        elapsed = time.perf_counter() - start
        if celery_task_duration is not None:
            celery_task_duration.labels(task_name=task_name).observe(elapsed)
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="success").inc()
        logger.info("[Task] recalculate_weights completed: %s", result)
        return result
    except Exception as exc:
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="failure").inc()
        logger.exception("[Task] recalculate_weights failed")
        raise self.retry(exc=exc)


async def _generate_forecasts():
    """전체 공항 예측 생성 (async)"""
    async with AsyncSessionLocal() as session:
        service = ForecastService(session)
        results = await service.forecast_all_airports(horizon=7)

    logger.info("Generated forecasts for %d airports", len(results))
    return {"airports_forecasted": len(results)}


@celery_app.task(
    name="app.tasks.collect_risks.generate_daily_forecasts",
    bind=True,
    max_retries=1,
    default_retry_delay=300,
)
def generate_daily_forecasts(self):
    """일일 예측 생성"""
    task_name = "daily_forecasts"
    logger.info("[Task] generate_daily_forecasts started")
    start = time.perf_counter()
    try:
        result = run_async(_generate_forecasts())
        elapsed = time.perf_counter() - start
        if celery_task_duration is not None:
            celery_task_duration.labels(task_name=task_name).observe(elapsed)
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="success").inc()
        logger.info("[Task] generate_daily_forecasts completed: %s", result)
        return result
    except Exception as exc:
        if celery_tasks_total is not None:
            celery_tasks_total.labels(task_name=task_name, status="failure").inc()
        logger.exception("[Task] generate_daily_forecasts failed")
        raise self.retry(exc=exc)
