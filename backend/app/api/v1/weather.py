"""
기상 데이터 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from app.collectors.weather import WeatherCollector
from app.schemas.weather import WeatherListResponse, WeatherSummaryResponse

router = APIRouter()


@router.get("", response_model=WeatherListResponse)
async def get_weather_data(
    airport_code: Optional[str] = Query(None, description="공항 코드 (예: ICN, GMP)"),
):
    """
    기상 데이터 조회

    - airport_code 없으면 전체 공항 데이터 반환
    - airport_code 있으면 해당 공항만 반환
    """
    async with WeatherCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="기상 데이터 수집에 실패했습니다.")

    data = result["data"]

    # 특정 공항 필터링
    if airport_code:
        airport_code = airport_code.upper()
        data = [d for d in data if d["airport_code"] == airport_code]

        if not data:
            raise HTTPException(status_code=404, detail=f"공항 코드 '{airport_code}'를 찾을 수 없습니다.")

    return {
        "collected_at": result["collected_at"],
        "count": len(data),
        "data": data,
    }


@router.get("/airports/{airport_code}")
async def get_airport_weather(airport_code: str):
    """특정 공항의 기상 데이터 조회"""
    airport_code = airport_code.upper()

    async with WeatherCollector() as collector:
        # 해당 공항이 존재하는지 확인
        if airport_code not in collector.AIRPORT_GRIDS:
            raise HTTPException(
                status_code=404,
                detail=f"공항 코드 '{airport_code}'를 찾을 수 없습니다."
            )

        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="기상 데이터 수집에 실패했습니다.")

    # 해당 공항 데이터 찾기
    airport_data = next(
        (d for d in result["data"] if d["airport_code"] == airport_code),
        None
    )

    if not airport_data:
        raise HTTPException(status_code=404, detail="기상 데이터를 찾을 수 없습니다.")

    return airport_data


@router.get("/summary", response_model=WeatherSummaryResponse)
async def get_weather_summary():
    """전체 공항 기상 요약"""
    async with WeatherCollector() as collector:
        result = await collector.run()

    if result["status"] != "success":
        raise HTTPException(status_code=500, detail="기상 데이터 수집에 실패했습니다.")

    data = result["data"]

    # 요약 통계 계산
    temps = [d["weather"].get("temperature") for d in data if d["weather"].get("temperature") is not None]
    winds = [d["weather"].get("wind_speed") for d in data if d["weather"].get("wind_speed") is not None]
    humidities = [d["weather"].get("humidity") for d in data if d["weather"].get("humidity") is not None]

    # 강풍 공항 찾기
    strong_wind_airports = [
        d["airport_code"] for d in data
        if d["weather"].get("is_strong_wind", False)
    ]

    # 강수 공항 찾기
    rainy_airports = [
        d["airport_code"] for d in data
        if d["weather"].get("precipitation_type", 0) not in [0, None, "0"]
    ]

    return {
        "collected_at": result["collected_at"],
        "airport_count": len(data),
        "statistics": {
            "temperature": {
                "min": round(min(temps), 1) if temps else None,
                "max": round(max(temps), 1) if temps else None,
                "avg": round(sum(temps) / len(temps), 1) if temps else None,
            },
            "wind_speed": {
                "min": round(min(winds), 1) if winds else None,
                "max": round(max(winds), 1) if winds else None,
                "avg": round(sum(winds) / len(winds), 1) if winds else None,
            },
            "humidity": {
                "min": round(min(humidities), 1) if humidities else None,
                "max": round(max(humidities), 1) if humidities else None,
                "avg": round(sum(humidities) / len(humidities), 1) if humidities else None,
            },
        },
        "alerts": {
            "strong_wind_airports": strong_wind_airports,
            "rainy_airports": rainy_airports,
        },
        "airports": [
            {
                "code": d["airport_code"],
                "name": d["airport_name"],
                "temperature": d["weather"].get("temperature"),
                "wind_speed": d["weather"].get("wind_speed"),
                "humidity": d["weather"].get("humidity"),
                "precipitation_type": d["weather"].get("precipitation_type_text", "없음"),
            }
            for d in data
        ],
    }
