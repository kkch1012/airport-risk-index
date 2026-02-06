"""
분석 관련 API 엔드포인트
"""

from fastapi import APIRouter
from datetime import datetime
import random

from app.schemas.analytics import (
    CorrelationResponse,
    WeightsResponse,
    TrendResponse,
    StatisticsResponse,
)

router = APIRouter()


@router.get("/correlations", response_model=CorrelationResponse)
async def get_correlation_analysis():
    """상관분석 결과 조회"""

    # 목업 상관분석 결과
    correlations = {
        "factors": {
            "visibility": {
                "incident_count": -0.42,
                "severity_score": -0.38,
                "significant": True,
            },
            "wind_speed": {
                "incident_count": 0.35,
                "severity_score": 0.41,
                "significant": True,
            },
            "wind_gust": {
                "incident_count": 0.28,
                "severity_score": 0.33,
                "significant": True,
            },
            "precipitation": {
                "incident_count": 0.22,
                "severity_score": 0.19,
                "significant": True,
            },
            "congestion_rate": {
                "incident_count": 0.31,
                "severity_score": 0.25,
                "significant": True,
            },
            "delay_rate": {
                "incident_count": 0.18,
                "severity_score": 0.15,
                "significant": False,
            },
            "disease_alert": {
                "incident_count": 0.12,
                "severity_score": 0.08,
                "significant": False,
            },
            "terror_threat": {
                "incident_count": 0.45,
                "severity_score": 0.52,
                "significant": True,
            },
        },
        "last_updated": "2024-01-15T03:00:00Z",
        "sample_size": 3650,
        "analysis_period": {
            "start": "2014-01-01",
            "end": "2023-12-31",
        }
    }

    return correlations


@router.get("/weights", response_model=WeightsResponse)
async def get_current_weights():
    """현재 적용 중인 가중치 조회"""

    weights = {
        "category_weights": {
            "aviation": 0.25,
            "security": 0.20,
            "health": 0.15,
            "operational": 0.15,
            "weather": 0.15,
            "external": 0.10,
        },
        "factor_weights": {
            "weather": {
                "visibility": 0.25,
                "wind_speed": 0.22,
                "wind_gust": 0.18,
                "precipitation": 0.15,
                "snowfall": 0.12,
                "thunderstorm": 0.08,
            },
            "operational": {
                "congestion_rate": 0.40,
                "delay_rate": 0.35,
                "cancellation_rate": 0.25,
            },
            "security": {
                "terror_threat_level": 0.50,
                "smuggling_cases": 0.30,
                "security_incidents": 0.20,
            },
        },
        "last_updated": "2024-01-15T03:00:00Z",
        "method": "ensemble",  # correlation, regression, rf, ensemble
    }

    return weights


@router.get("/trends", response_model=TrendResponse)
async def get_trend_analysis(
    airport_code: str = None,
    category: str = None,
    period: str = "1M",  # 1W, 1M, 3M, 6M, 1Y
):
    """트렌드 분석"""

    # 기간별 데이터 포인트 수
    period_points = {
        "1W": 7,
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365,
    }

    points = period_points.get(period, 30)

    # 목업 트렌드 데이터
    random.seed(42)
    trend_data = []
    base_score = 35

    for i in range(min(points, 60)):  # 최대 60개 포인트
        score = base_score + random.uniform(-5, 5) + (i * 0.05)  # 약간의 상승 트렌드
        trend_data.append({
            "day": i,
            "score": round(score, 2),
        })

    return {
        "airport_code": airport_code or "ALL",
        "category": category or "total",
        "period": period,
        "data": trend_data,
        "statistics": {
            "average": round(sum(d["score"] for d in trend_data) / len(trend_data), 2),
            "min": round(min(d["score"] for d in trend_data), 2),
            "max": round(max(d["score"] for d in trend_data), 2),
            "trend": "increasing",
        }
    }


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """전체 통계"""

    return {
        "overview": {
            "total_data_points": 1250000,
            "analysis_start_date": "2014-01-01",
            "last_incident_date": "2024-01-10",
            "total_incidents": 342,
        },
        "by_category": {
            "aviation": {"incidents": 45, "avg_severity": 3.2},
            "security": {"incidents": 78, "avg_severity": 2.1},
            "health": {"incidents": 156, "avg_severity": 1.8},
            "operational": {"incidents": 23, "avg_severity": 1.5},
            "weather": {"incidents": 32, "avg_severity": 2.8},
            "external": {"incidents": 8, "avg_severity": 2.4},
        },
        "by_airport": {
            "ICN": {"incidents": 89, "risk_days": 45},
            "GMP": {"incidents": 67, "risk_days": 38},
            "PUS": {"incidents": 54, "risk_days": 42},
            "CJU": {"incidents": 78, "risk_days": 55},
        },
        "updated_at": datetime.now().isoformat(),
    }
