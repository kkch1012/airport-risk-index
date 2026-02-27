"""
위험지수 관련 API 엔드포인트
"""

import asyncio
import logging
import re

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date, datetime

from app.collectors.weather import WeatherCollector
from app.collectors.travel_advisory import TravelAdvisoryCollector
from app.collectors.health_risk import HealthRiskCollector
from app.collectors.flight_status import FlightStatusCollector
from app.collectors.aviation_safety import AviationSafetyCollector
from app.services.risk_calculator import RiskCalculator
from app.services.risk_history_service import RiskHistoryService
from app.services.weight_service import WeightService
from app.core.database import AsyncSessionLocal
from app.core.constants import AIRPORT_NAMES

# 공항 코드 형식 검증 패턴
_AIRPORT_CODE_RE = re.compile(r"^[A-Z]{3,4}$")
from app.schemas.risks import (
    DashboardResponse,
    AirportRiskResponse,
    RiskHistoryResponse,
    ComparisonResponse,
    TravelAdvisoryResponse,
    HealthRiskResponse,
    AirportHealthRiskResponse,
    FlightStatusResponse,
    AirportFlightStatusResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_calculator() -> RiskCalculator:
    """동적 가중치를 로드한 RiskCalculator 생성"""
    try:
        async with AsyncSessionLocal() as session:
            service = WeightService(session)
            weights = await service.get_active_category_weights()
        return RiskCalculator(custom_weights=weights)
    except Exception:
        return RiskCalculator()


async def get_weather_data_map() -> dict:
    """기상 데이터를 공항 코드별로 매핑하여 반환"""
    async with WeatherCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        return {}

    # 공항 코드를 키로 하는 딕셔너리 생성
    weather_map = {}
    for data in result["data"]:
        airport_code = data["airport_code"]
        weather_map[airport_code] = data["weather"]

    return weather_map


async def get_travel_advisory_data() -> tuple[list, bool]:
    """여행경보 데이터 수집 및 반환"""
    async with TravelAdvisoryCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        return [], False

    is_real_data = bool(collector.api_key)
    return result["data"], is_real_data


async def get_health_data() -> tuple[list, bool]:
    """보건위험(검역관리지역) 데이터 수집 및 반환"""
    async with HealthRiskCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        return [], False

    is_real_data = bool(collector.api_key)
    return result["data"], is_real_data


async def get_operational_data() -> tuple[list, bool]:
    """운영위험(항공편 운항정보) 데이터 수집 및 반환"""
    async with FlightStatusCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        return [], False

    is_real_data = bool(collector.api_key)
    return result["data"], is_real_data


async def get_aviation_data() -> tuple[list, bool]:
    """항공안전(ARAIB 사고) 데이터 수집 및 반환"""
    async with AviationSafetyCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        return [], False

    is_real_data = collector.can_crawl
    return result["data"], is_real_data


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard():
    """대시보드 전체 현황"""
    calculator = await _get_calculator()

    # 모든 수집기를 병렬로 실행
    weather_map, \
        (travel_advisory_data, is_advisory_real), \
        (health_data, is_health_real), \
        (operational_data, is_operational_real), \
        (aviation_data, is_aviation_real) = await asyncio.gather(
        get_weather_data_map(),
        get_travel_advisory_data(),
        get_health_data(),
        get_operational_data(),
        get_aviation_data(),
    )

    airport_data = []
    risk_results = []
    for code, name in AIRPORT_NAMES.items():
        # 기상 데이터가 있으면 실제 데이터 사용
        weather_data = weather_map.get(code)

        # 위험지수 계산
        risk_result = calculator.calculate_total_risk(
            airport_code=code,
            airport_name=name,
            weather_data=weather_data,
            travel_advisory_data=travel_advisory_data,
            health_data=health_data,
            operational_data=operational_data,
            aviation_data=aviation_data
        )

        risk_results.append(risk_result)
        airport_data.append({
            "code": code,
            "name": name,
            "score": risk_result.total_score,
            "level": risk_result.risk_level,
            "weather_score": risk_result.categories["weather"].score,
            "external_score": risk_result.categories["external"].score,
            "health_score": risk_result.categories["health"].score,
            "operational_score": risk_result.categories["operational"].score,
            "aviation_score": risk_result.categories["aviation"].score,
        })

    # DB 이력 저장 (실패해도 API 응답에 영향 없음)
    try:
        async with AsyncSessionLocal() as session:
            service = RiskHistoryService(session)
            saved = await service.save_batch(risk_results)
            logger.info("Saved %d/%d risk assessments to DB", saved, len(risk_results))
    except Exception:
        logger.exception("Failed to save risk assessments to DB")

    # 점수순 정렬 (높은 순)
    airport_data.sort(key=lambda x: x["score"], reverse=True)

    # 통계 계산
    high_risk_count = sum(1 for a in airport_data if a["level"] in ["HIGH", "CRITICAL"])
    avg_score = sum(a["score"] for a in airport_data) / len(airport_data)

    # 알림 생성 (기상 + 여행경보 + 보건 + 운영)
    now = datetime.now()
    alerts = []

    # 기상 관련 알림 — 구체적 기상 정보 포함
    for airport in airport_data:
        if airport["weather_score"] >= 50:
            weather_detail = weather_map.get(airport["code"], {})
            msg_parts = []
            wind = weather_detail.get("wind_speed")
            precip = weather_detail.get("precipitation")
            humidity = weather_detail.get("humidity")
            precip_type = weather_detail.get("precipitation_type", 0)

            precip_labels = {1: "비", 2: "비/눈", 3: "눈", 5: "빗방울", 7: "눈날림"}

            if wind and wind >= 10:
                msg_parts.append(f"강풍 {wind:.1f}m/s")
            if precip and precip > 0:
                label = precip_labels.get(precip_type, "강수")
                msg_parts.append(f"{label} {precip:.1f}mm")
            if humidity and humidity >= 85:
                msg_parts.append(f"습도 {humidity}%")

            if msg_parts:
                message = f"{airport['name']} {', '.join(msg_parts)} (위험도 {airport['weather_score']:.0f})"
            else:
                score = airport["weather_score"]
                if score >= 70:
                    message = f"{airport['name']} 기상 악화 경고 (위험도 {score:.0f})"
                else:
                    message = f"{airport['name']} 기상 주의보 발령 (위험도 {score:.0f})"

            alerts.append({
                "airport": airport["code"],
                "type": "WEATHER",
                "message": message,
                "severity": "WARNING" if airport["weather_score"] < 70 else "CRITICAL",
                "created_at": now.isoformat(),
            })

    # 여행경보 관련 알림 — 경보 단계 및 지역 정보 포함
    high_risk_advisories = [
        d for d in travel_advisory_data
        if d.get("alarm_level", 0) >= 3
    ]
    # 높은 경보 우선
    high_risk_advisories.sort(key=lambda x: x.get("alarm_level", 0), reverse=True)
    for advisory in high_risk_advisories[:3]:
        level = advisory.get("alarm_level", 3)
        country = advisory["country_name"]
        alarm_name = advisory.get("alarm_name", "")
        region = advisory.get("region_type", "전지역")

        if level >= 4:
            message = f"[{alarm_name}] {country} ({region}) — 즉시 대피 권고"
        else:
            message = f"[{alarm_name}] {country} ({region}) — 출국 자제 권고"

        alerts.append({
            "airport": "국제선",
            "type": "SECURITY",
            "message": message,
            "severity": "CRITICAL" if level >= 4 else "WARNING",
            "created_at": now.isoformat(),
        })

    # 보건위험 관련 알림 — 질병명 및 위험도 포함
    high_risk_health = [
        d for d in health_data
        if d.get("risk_score", 0) >= 70
    ]
    high_risk_health.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    for health_item in high_risk_health[:2]:
        country = health_item.get("country_name", "")
        disease = health_item.get("disease_name", "")
        score = health_item.get("risk_score", 0)

        if score >= 85:
            message = f"검역 강화: {country} {disease} 확산 중 — 입국자 전수검사"
        else:
            message = f"검역 주의: {country} {disease} 감시 강화 (위험도 {score:.0f})"

        alerts.append({
            "airport": "검역",
            "type": "HEALTH",
            "message": message,
            "severity": "CRITICAL" if score >= 85 else "WARNING",
            "created_at": now.isoformat(),
        })

    # 운영위험 알림 — 지연/결항 높은 공항
    for airport in airport_data:
        op_score = airport.get("operational_score", 0)
        if op_score >= 55:
            if op_score >= 70:
                message = f"{airport['name']} 운항 지연 다수 발생 중 (운영위험 {op_score:.0f})"
            else:
                message = f"{airport['name']} 일부 항공편 지연 (운영위험 {op_score:.0f})"
            alerts.append({
                "airport": airport["code"],
                "type": "OPERATIONAL",
                "message": message,
                "severity": "WARNING" if op_score < 70 else "CRITICAL",
                "created_at": now.isoformat(),
            })

    # 심각도 우선 정렬 (CRITICAL > WARNING > INFO)
    severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    alerts.sort(key=lambda x: severity_order.get(x["severity"], 9))

    return {
        "summary": {
            "total_airports": len(AIRPORT_NAMES),
            "high_risk_count": high_risk_count,
            "average_score": round(avg_score, 2),
            "updated_at": datetime.now().isoformat(),
        },
        "airports": airport_data,
        "alerts": alerts[:5],  # 최대 5개
        "data_sources": {
            "weather": "실제 데이터" if weather_map else "목업 데이터",
            "travel_advisory": "실제 데이터" if is_advisory_real else "목업 데이터",
            "health": "실제 데이터" if is_health_real else "목업 데이터",
            "operational": "실제 데이터" if is_operational_real else "목업 데이터",
            "aviation": "실제 데이터" if is_aviation_real else "목업 데이터",
        }
    }


@router.get("/airports/{airport_code}", response_model=AirportRiskResponse)
async def get_airport_risk(
    airport_code: str,
    target_date: Optional[date] = None,
):
    """특정 공항의 상세 위험지수"""
    airport_code = airport_code.upper()

    if airport_code not in AIRPORT_NAMES:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    calculator = await _get_calculator()

    # 실제 기상 데이터 수집
    weather_map = await get_weather_data_map()
    weather_data = weather_map.get(airport_code)

    # 여행경보 데이터 수집
    travel_advisory_data, is_advisory_real = await get_travel_advisory_data()

    # 보건위험 데이터 수집
    health_data, is_health_real = await get_health_data()

    # 운영위험 데이터 수집
    operational_data, is_operational_real = await get_operational_data()

    # 항공안전 데이터 수집
    aviation_data, is_aviation_real = await get_aviation_data()

    # 위험지수 계산
    risk_result = calculator.calculate_total_risk(
        airport_code=airport_code,
        airport_name=AIRPORT_NAMES[airport_code],
        weather_data=weather_data,
        travel_advisory_data=travel_advisory_data,
        health_data=health_data,
        operational_data=operational_data,
        aviation_data=aviation_data
    )

    # 카테고리 데이터를 딕셔너리로 변환
    categories = {}
    for code, cat_score in risk_result.categories.items():
        categories[code] = {
            "name": cat_score.name,
            "score": cat_score.score,
            "level": cat_score.level,
            "factors": cat_score.factors,
        }

    return {
        "airport": {
            "code": airport_code,
            "name": AIRPORT_NAMES[airport_code],
        },
        "date": (target_date or date.today()).isoformat(),
        "total_score": risk_result.total_score,
        "risk_level": risk_result.risk_level,
        "categories": categories,
        "updated_at": risk_result.updated_at,
        "data_source": {
            "weather": "실제 데이터" if weather_data else "목업 데이터",
            "travel_advisory": "실제 데이터" if is_advisory_real else "목업 데이터",
            "health": "실제 데이터" if is_health_real else "목업 데이터",
            "operational": "실제 데이터" if is_operational_real else "목업 데이터",
            "aviation": "실제 데이터" if is_aviation_real else "목업 데이터",
            "security": "목업 데이터 (추후 연동 예정)",
        }
    }


@router.get("/airports/{airport_code}/history", response_model=RiskHistoryResponse)
async def get_risk_history(
    airport_code: str,
    start_date: date,
    end_date: date,
    page: int = Query(1, ge=1, le=10000),
    page_size: int = Query(50, ge=1, le=200),
):
    """위험지수 이력 조회 (DB 기반, 페이지네이션 지원)"""
    airport_code = airport_code.upper()

    if airport_code not in AIRPORT_NAMES:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="시작일이 종료일보다 늦을 수 없습니다.")

    offset = (page - 1) * page_size

    async with AsyncSessionLocal() as session:
        service = RiskHistoryService(session)
        total = await service.get_history_count(airport_code, start_date, end_date)
        assessments = await service.get_history(
            airport_code, start_date, end_date,
            limit=page_size, offset=offset,
        )

    history = [
        {
            "date": a.assessed_date.isoformat(),
            "total_score": round(a.total_score, 2),
            "risk_level": a.risk_level,
        }
        for a in assessments
    ]

    return {
        "airport_code": airport_code,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "history": history,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        },
    }


@router.get("/comparison", response_model=ComparisonResponse)
async def compare_airports(
    airport_codes: List[str] = Query(..., max_length=15),
):
    """공항 간 비교"""
    if len(airport_codes) > 15:
        raise HTTPException(status_code=400, detail="최대 15개 공항까지 비교 가능합니다.")

    calculator = await _get_calculator()
    weather_map = await get_weather_data_map()
    travel_advisory_data, _ = await get_travel_advisory_data()
    health_data, _ = await get_health_data()
    operational_data, _ = await get_operational_data()
    aviation_data, _ = await get_aviation_data()

    comparison = []
    for code in airport_codes:
        code = code.upper()
        if code not in AIRPORT_NAMES:
            continue

        weather_data = weather_map.get(code)
        risk_result = calculator.calculate_total_risk(
            airport_code=code,
            airport_name=AIRPORT_NAMES[code],
            weather_data=weather_data,
            travel_advisory_data=travel_advisory_data,
            health_data=health_data,
            operational_data=operational_data,
            aviation_data=aviation_data
        )

        comparison.append({
            "code": code,
            "name": AIRPORT_NAMES[code],
            "total_score": risk_result.total_score,
            "categories": {
                cat_code: cat_score.score
                for cat_code, cat_score in risk_result.categories.items()
            },
        })

    return {
        "date": date.today().isoformat(),
        "comparison": comparison,
    }


@router.get("/travel-advisory", response_model=TravelAdvisoryResponse)
async def get_travel_advisory():
    """여행경보 현황 조회"""
    async with TravelAdvisoryCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="여행경보 데이터 수집 실패")

    # 요약 통계 생성
    summary = collector.get_summary(result["data"])

    return {
        "updated_at": datetime.now().isoformat(),
        "data_source": "실제 데이터" if collector.api_key else "목업 데이터",
        "summary": summary,
        "countries": result["data"],
    }


@router.get("/health-risk", response_model=HealthRiskResponse)
async def get_health_risk():
    """보건위험(검역관리지역) 현황 조회"""
    async with HealthRiskCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="보건위험 데이터 수집 실패")

    # 요약 통계 생성
    summary = collector.get_summary(result["data"])

    return {
        "updated_at": datetime.now().isoformat(),
        "data_source": "실제 데이터" if collector.api_key else "목업 데이터",
        "summary": summary,
        "quarantine_regions": result["data"],
    }


@router.get("/health-risk/airports/{airport_code}", response_model=AirportHealthRiskResponse)
async def get_airport_health_risk(airport_code: str):
    """특정 공항의 보건위험 상세 조회"""
    airport_code = airport_code.upper()

    if airport_code not in AIRPORT_NAMES:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    # 공항별 취항 국가 (risk_calculator에서 가져옴)
    from app.services.risk_calculator import AIRPORT_INTERNATIONAL_ROUTES

    async with HealthRiskCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="보건위험 데이터 수집 실패")

    # 공항별 보건위험 계산
    airport_health_risk = collector.calculate_airport_health_risk(
        airport_code=airport_code,
        data_list=result["data"],
        airport_routes=AIRPORT_INTERNATIONAL_ROUTES
    )

    return {
        "updated_at": datetime.now().isoformat(),
        "data_source": "실제 데이터" if collector.api_key else "목업 데이터",
        "airport": {
            "code": airport_code,
            "name": AIRPORT_NAMES[airport_code],
        },
        **airport_health_risk,
    }


@router.get("/flight-status", response_model=FlightStatusResponse)
async def get_flight_status():
    """운영위험(항공편 운항현황) 조회"""
    async with FlightStatusCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="운항정보 데이터 수집 실패")

    # 요약 통계 생성
    summary = collector.get_summary(result["data"])

    return {
        "updated_at": datetime.now().isoformat(),
        "data_source": "실제 데이터" if collector.api_key else "목업 데이터",
        "summary": summary,
        "airports": result["data"],
    }


@router.get("/flight-status/airports/{airport_code}", response_model=AirportFlightStatusResponse)
async def get_airport_flight_status(airport_code: str):
    """특정 공항의 운항현황 상세 조회"""
    airport_code = airport_code.upper()

    if airport_code not in AIRPORT_NAMES:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    async with FlightStatusCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="운항정보 데이터 수집 실패")

    # 해당 공항 데이터 찾기
    airport_data = None
    for data in result["data"]:
        if data.get("airport_code") == airport_code:
            airport_data = collector.transform(data) if data.get("departures") or data.get("arrivals") else data
            break

    if not airport_data:
        airport_data = {
            "airport_code": airport_code,
            "airport_name": AIRPORT_NAMES[airport_code],
            "message": "운항 데이터 없음",
        }

    return {
        "updated_at": datetime.now().isoformat(),
        "data_source": "실제 데이터" if collector.api_key else "목업 데이터",
        "airport": {
            "code": airport_code,
            "name": AIRPORT_NAMES[airport_code],
        },
        **airport_data,
    }
