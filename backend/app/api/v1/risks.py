"""
위험지수 관련 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import date, datetime
import random

router = APIRouter()


def generate_mock_risk_data(airport_code: str):
    """목업 위험지수 데이터 생성"""
    random.seed(hash(airport_code + str(date.today())))

    categories = {
        "aviation": {
            "name": "항공안전",
            "score": random.uniform(10, 60),
            "factors": {
                "incident_history": random.uniform(5, 40),
                "near_miss": random.uniform(10, 50),
                "bird_strike": random.uniform(5, 30),
            }
        },
        "security": {
            "name": "보안위협",
            "score": random.uniform(15, 55),
            "factors": {
                "terror_threat": random.uniform(10, 40),
                "smuggling": random.uniform(5, 30),
                "illegal_entry": random.uniform(10, 35),
            }
        },
        "health": {
            "name": "보건위험",
            "score": random.uniform(20, 50),
            "factors": {
                "disease_alert": random.uniform(10, 45),
                "quarantine_cases": random.uniform(5, 25),
            }
        },
        "operational": {
            "name": "운영위험",
            "score": random.uniform(25, 65),
            "factors": {
                "congestion": random.uniform(30, 80),
                "delay_rate": random.uniform(10, 40),
                "cancellation": random.uniform(5, 20),
            }
        },
        "weather": {
            "name": "기상위험",
            "score": random.uniform(15, 70),
            "factors": {
                "visibility": random.uniform(10, 50),
                "wind_speed": random.uniform(5, 40),
                "precipitation": random.uniform(0, 30),
            }
        },
        "external": {
            "name": "외부요인",
            "score": random.uniform(10, 45),
            "factors": {
                "travel_advisory": random.uniform(5, 30),
                "geopolitical": random.uniform(10, 40),
            }
        },
    }

    # 카테고리별 점수에 레벨 추가
    for cat in categories.values():
        score = cat["score"]
        if score < 25:
            cat["level"] = "LOW"
        elif score < 50:
            cat["level"] = "MODERATE"
        elif score < 75:
            cat["level"] = "HIGH"
        else:
            cat["level"] = "CRITICAL"

    # 가중치
    weights = {
        "aviation": 0.25,
        "security": 0.20,
        "health": 0.15,
        "operational": 0.15,
        "weather": 0.15,
        "external": 0.10,
    }

    # 종합 점수 계산
    total_score = sum(
        categories[cat]["score"] * weights[cat]
        for cat in categories
    )

    return {
        "total_score": round(total_score, 2),
        "categories": categories,
    }


@router.get("/dashboard")
async def get_dashboard():
    """대시보드 전체 현황"""
    airports = ["ICN", "GMP", "PUS", "CJU", "TAE", "CJJ", "KWJ", "RSU", "USN", "KPO", "WJU", "YNY", "HIN", "KUV", "MWX"]
    airport_names = {
        "ICN": "인천국제공항", "GMP": "김포국제공항", "PUS": "김해국제공항",
        "CJU": "제주국제공항", "TAE": "대구국제공항", "CJJ": "청주국제공항",
        "KWJ": "광주공항", "RSU": "여수공항", "USN": "울산공항",
        "KPO": "포항경주공항", "WJU": "원주공항", "YNY": "양양국제공항",
        "HIN": "사천공항", "KUV": "군산공항", "MWX": "무안국제공항",
    }

    airport_data = []
    for code in airports:
        risk = generate_mock_risk_data(code)
        score = risk["total_score"]

        if score < 25:
            level = "LOW"
        elif score < 50:
            level = "MODERATE"
        elif score < 75:
            level = "HIGH"
        else:
            level = "CRITICAL"

        airport_data.append({
            "code": code,
            "name": airport_names[code],
            "score": score,
            "level": level,
        })

    # 점수순 정렬
    airport_data.sort(key=lambda x: x["score"], reverse=True)

    # 통계 계산
    high_risk_count = sum(1 for a in airport_data if a["level"] in ["HIGH", "CRITICAL"])
    avg_score = sum(a["score"] for a in airport_data) / len(airport_data)

    return {
        "summary": {
            "total_airports": len(airports),
            "high_risk_count": high_risk_count,
            "average_score": round(avg_score, 2),
            "updated_at": datetime.now().isoformat(),
        },
        "airports": airport_data,
        "alerts": [
            {"airport": "PUS", "type": "WEATHER", "message": "강풍 주의보 발효 중", "severity": "WARNING"},
            {"airport": "ICN", "type": "HEALTH", "message": "검역 강화 구간 운영 중", "severity": "INFO"},
        ]
    }


@router.get("/airports/{airport_code}")
async def get_airport_risk(
    airport_code: str,
    target_date: Optional[date] = None,
):
    """특정 공항의 상세 위험지수"""
    airport_code = airport_code.upper()

    airport_names = {
        "ICN": "인천국제공항", "GMP": "김포국제공항", "PUS": "김해국제공항",
        "CJU": "제주국제공항", "TAE": "대구국제공항", "CJJ": "청주국제공항",
        "KWJ": "광주공항", "RSU": "여수공항", "USN": "울산공항",
        "KPO": "포항경주공항", "WJU": "원주공항", "YNY": "양양국제공항",
        "HIN": "사천공항", "KUV": "군산공항", "MWX": "무안국제공항",
    }

    if airport_code not in airport_names:
        raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")

    risk = generate_mock_risk_data(airport_code)

    # 종합 레벨 계산
    score = risk["total_score"]
    if score < 25:
        level = "LOW"
    elif score < 50:
        level = "MODERATE"
    elif score < 75:
        level = "HIGH"
    else:
        level = "CRITICAL"

    return {
        "airport": {
            "code": airport_code,
            "name": airport_names[airport_code],
        },
        "date": (target_date or date.today()).isoformat(),
        "total_score": risk["total_score"],
        "risk_level": level,
        "categories": risk["categories"],
        "updated_at": datetime.now().isoformat(),
    }


@router.get("/airports/{airport_code}/history")
async def get_risk_history(
    airport_code: str,
    start_date: date,
    end_date: date,
):
    """위험지수 이력 조회"""
    airport_code = airport_code.upper()

    # 목업 이력 데이터 생성
    history = []
    current = start_date

    while current <= end_date:
        random.seed(hash(airport_code + str(current)))
        score = random.uniform(20, 60)

        history.append({
            "date": current.isoformat(),
            "total_score": round(score, 2),
        })

        current = date(current.year, current.month, current.day + 1) if current.day < 28 else date(current.year, current.month + 1 if current.month < 12 else 1, 1)

    return {
        "airport_code": airport_code,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "history": history[:30],  # 최대 30일
    }


@router.get("/comparison")
async def compare_airports(
    airport_codes: List[str] = Query(...),
):
    """공항 간 비교"""
    airport_names = {
        "ICN": "인천국제공항", "GMP": "김포국제공항", "PUS": "김해국제공항",
        "CJU": "제주국제공항", "TAE": "대구국제공항", "CJJ": "청주국제공항",
    }

    comparison = []
    for code in airport_codes:
        code = code.upper()
        if code not in airport_names:
            continue

        risk = generate_mock_risk_data(code)
        comparison.append({
            "code": code,
            "name": airport_names.get(code, code),
            "total_score": risk["total_score"],
            "categories": {k: v["score"] for k, v in risk["categories"].items()},
        })

    return {
        "date": date.today().isoformat(),
        "comparison": comparison,
    }
