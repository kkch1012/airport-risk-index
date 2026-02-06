"""
위험지수 관련 API 엔드포인트
"""

import logging

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

    # 실제 기상 데이터 수집
    weather_map = await get_weather_data_map()

    # 여행경보 데이터 수집
    travel_advisory_data, is_advisory_real = await get_travel_advisory_data()

    # 보건위험 데이터 수집
    health_data, is_health_real = await get_health_data()

    # 운영위험 데이터 수집
    operational_data, is_operational_real = await get_operational_data()

    # 항공안전 데이터 수집
    aviation_data, is_aviation_real = await get_aviation_data()

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

    # 알림 생성 (기상 + 여행경보)
    alerts = []

    # 기상 관련 알림
    for airport in airport_data:
        if airport["weather_score"] >= 50:
            alerts.append({
                "airport": airport["code"],
                "type": "WEATHER",
                "message": f"기상 위험지수 높음 ({airport['weather_score']:.1f})",
                "severity": "WARNING" if airport["weather_score"] < 70 else "CRITICAL"
            })

    # 여행경보 관련 알림
    high_risk_advisories = [
        d for d in travel_advisory_data
        if d.get("alarm_level", 0) >= 3
    ]
    for advisory in high_risk_advisories[:3]:  # 최대 3개
        alerts.append({
            "airport": "국제선",
            "type": "SECURITY",
            "message": f"{advisory['country_name']} {advisory['alarm_name']}",
            "severity": "CRITICAL" if advisory.get("alarm_level", 0) >= 4 else "WARNING"
        })

    # 보건위험 관련 알림
    high_risk_health = [
        d for d in health_data
        if d.get("risk_score", 0) >= 70
    ]
    for health_item in high_risk_health[:2]:  # 최대 2개
        alerts.append({
            "airport": "검역",
            "type": "HEALTH",
            "message": f"{health_item.get('country_name', '')} {health_item.get('disease_name', '')} 경보",
            "severity": "CRITICAL" if health_item.get("risk_score", 0) >= 85 else "WARNING"
        })

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
    page: int = 1,
    page_size: int = 50,
):
    """위험지수 이력 조회 (DB 기반, 페이지네이션 지원)"""
    airport_code = airport_code.upper()

    if airport_code not in AIRPORT_NAMES:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    page_size = min(page_size, 200)  # 최대 200건
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
    airport_codes: List[str] = Query(...),
):
    """공항 간 비교"""
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
