"""
위험지수 관련 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date, datetime

from app.collectors.weather import WeatherCollector
from app.collectors.travel_advisory import TravelAdvisoryCollector
from app.services.risk_calculator import RiskCalculator

router = APIRouter()

# 공항 정보
AIRPORT_NAMES = {
    "ICN": "인천국제공항", "GMP": "김포국제공항", "PUS": "김해국제공항",
    "CJU": "제주국제공항", "TAE": "대구국제공항", "CJJ": "청주국제공항",
    "KWJ": "광주공항", "RSU": "여수공항", "USN": "울산공항",
    "KPO": "포항경주공항", "WJU": "원주공항", "YNY": "양양국제공항",
    "HIN": "사천공항", "KUV": "군산공항", "MWX": "무안국제공항",
}


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


@router.get("/dashboard")
async def get_dashboard():
    """대시보드 전체 현황"""
    calculator = RiskCalculator()

    # 실제 기상 데이터 수집
    weather_map = await get_weather_data_map()

    # 여행경보 데이터 수집
    travel_advisory_data, is_advisory_real = await get_travel_advisory_data()

    airport_data = []
    for code, name in AIRPORT_NAMES.items():
        # 기상 데이터가 있으면 실제 데이터 사용
        weather_data = weather_map.get(code)

        # 위험지수 계산
        risk_result = calculator.calculate_total_risk(
            airport_code=code,
            airport_name=name,
            weather_data=weather_data,
            travel_advisory_data=travel_advisory_data
        )

        airport_data.append({
            "code": code,
            "name": name,
            "score": risk_result.total_score,
            "level": risk_result.risk_level,
            "weather_score": risk_result.categories["weather"].score,
            "external_score": risk_result.categories["external"].score,
        })

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
        }
    }


@router.get("/airports/{airport_code}")
async def get_airport_risk(
    airport_code: str,
    target_date: Optional[date] = None,
):
    """특정 공항의 상세 위험지수"""
    airport_code = airport_code.upper()

    if airport_code not in AIRPORT_NAMES:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    calculator = RiskCalculator()

    # 실제 기상 데이터 수집
    weather_map = await get_weather_data_map()
    weather_data = weather_map.get(airport_code)

    # 여행경보 데이터 수집
    travel_advisory_data, is_advisory_real = await get_travel_advisory_data()

    # 위험지수 계산
    risk_result = calculator.calculate_total_risk(
        airport_code=airport_code,
        airport_name=AIRPORT_NAMES[airport_code],
        weather_data=weather_data,
        travel_advisory_data=travel_advisory_data
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
            "others": "목업 데이터 (추후 연동 예정)",
        }
    }


@router.get("/airports/{airport_code}/history")
async def get_risk_history(
    airport_code: str,
    start_date: date,
    end_date: date,
):
    """위험지수 이력 조회 (현재 목업)"""
    airport_code = airport_code.upper()

    if airport_code not in AIRPORT_NAMES:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    # 목업 이력 데이터 생성
    import random
    history = []
    current = start_date
    days = 0

    while current <= end_date and days < 30:
        random.seed(hash(airport_code + str(current)))
        score = random.uniform(20, 60)

        history.append({
            "date": current.isoformat(),
            "total_score": round(score, 2),
        })

        days += 1
        from datetime import timedelta
        current = current + timedelta(days=1)

    return {
        "airport_code": airport_code,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "history": history,
    }


@router.get("/comparison")
async def compare_airports(
    airport_codes: List[str] = Query(...),
):
    """공항 간 비교"""
    calculator = RiskCalculator()
    weather_map = await get_weather_data_map()
    travel_advisory_data, _ = await get_travel_advisory_data()

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
            travel_advisory_data=travel_advisory_data
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


@router.get("/travel-advisory")
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
