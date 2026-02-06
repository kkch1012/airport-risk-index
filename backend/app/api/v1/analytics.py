"""
분석 관련 API 엔드포인트
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.ml.weight_calculator import DEFAULT_CATEGORY_WEIGHTS
from app.models.risk_history import CategoryScoreRecord, RiskAssessment
from app.schemas.analytics import (
    CorrelationMatrixResponse,
    CorrelationResponse,
    StatisticsResponse,
    TimeSeriesResponse,
    TrendResponse,
    WeightsResponse,
)
from app.services.analytics_service import AnalyticsService
from app.services.weight_service import WeightService

router = APIRouter()

# 데이터 부족 시 사용할 기본 상관분석 결과
_DEFAULT_CORRELATIONS = {
    "factors": {
        "weather": {"incident_count": 0.0, "severity_score": 0.0, "significant": False},
        "aviation": {"incident_count": 0.0, "severity_score": 0.0, "significant": False},
        "security": {"incident_count": 0.0, "severity_score": 0.0, "significant": False},
        "health": {"incident_count": 0.0, "severity_score": 0.0, "significant": False},
        "operational": {"incident_count": 0.0, "severity_score": 0.0, "significant": False},
        "external": {"incident_count": 0.0, "severity_score": 0.0, "significant": False},
    },
    "last_updated": "",
    "sample_size": 0,
    "analysis_period": {"start": "", "end": ""},
}


@router.get("/correlations", response_model=CorrelationResponse)
async def get_correlation_analysis(db: AsyncSession = Depends(get_db)):
    """상관분석 결과 조회"""
    service = WeightService(db)
    analysis = await service.run_correlation_analysis()

    if "error" in analysis:
        result = _DEFAULT_CORRELATIONS.copy()
        result["last_updated"] = datetime.now().isoformat()
        return result

    # factor_correlations → CorrelationResponse 변환
    factors = {}
    for name, corr_data in analysis["factor_correlations"].items():
        if corr_data.get("insufficient_data"):
            factors[name] = {
                "incident_count": 0.0,
                "severity_score": 0.0,
                "significant": False,
            }
        else:
            factors[name] = {
                "incident_count": corr_data.get("pearson_r", 0.0),
                "severity_score": corr_data.get("spearman_r", 0.0),
                "significant": corr_data.get("significant", False),
            }

    return {
        "factors": factors,
        "last_updated": datetime.now().isoformat(),
        "sample_size": analysis.get("sample_size", 0),
        "analysis_period": analysis.get("analysis_period", {"start": "", "end": ""}),
    }


@router.get("/weights", response_model=WeightsResponse)
async def get_current_weights(db: AsyncSession = Depends(get_db)):
    """현재 적용 중인 가중치 조회"""
    service = WeightService(db)
    active = await service.get_active_weights()

    if active:
        return {
            "category_weights": active.category_weights,
            "factor_weights": active.factor_weights or {},
            "last_updated": active.calculated_at.isoformat(),
            "method": active.method,
        }

    return {
        "category_weights": DEFAULT_CATEGORY_WEIGHTS,
        "factor_weights": {},
        "last_updated": datetime.now().isoformat(),
        "method": "default",
    }


@router.get("/trends", response_model=TrendResponse)
async def get_trend_analysis(
    airport_code: Optional[str] = None,
    category: Optional[str] = None,
    period: str = "1M",
    db: AsyncSession = Depends(get_db),
):
    """트렌드 분석"""
    period_days = {"1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    days = period_days.get(period, 30)
    cutoff = datetime.now().date() - timedelta(days=days)

    # 쿼리: 날짜별 평균 점수
    if category and category != "total":
        # 특정 카테고리 트렌드
        stmt = (
            select(
                RiskAssessment.assessed_date,
                func.avg(CategoryScoreRecord.score).label("avg_score"),
            )
            .join(
                CategoryScoreRecord,
                CategoryScoreRecord.assessment_id == RiskAssessment.id,
            )
            .where(
                RiskAssessment.assessed_date >= cutoff,
                CategoryScoreRecord.category_code == category,
            )
        )
    else:
        # 전체 total_score 트렌드
        stmt = select(
            RiskAssessment.assessed_date,
            func.avg(RiskAssessment.total_score).label("avg_score"),
        ).where(RiskAssessment.assessed_date >= cutoff)

    if airport_code:
        stmt = stmt.where(RiskAssessment.airport_code == airport_code)

    stmt = stmt.group_by(RiskAssessment.assessed_date).order_by(RiskAssessment.assessed_date)

    result = await db.execute(stmt)
    rows = result.all()

    trend_data = []
    for i, row in enumerate(rows):
        trend_data.append({"day": i, "score": round(float(row.avg_score), 2)})

    if trend_data:
        scores = [d["score"] for d in trend_data]
        avg_score = sum(scores) / len(scores)
        # 단순 트렌드 판단: 전반부 vs 후반부
        mid = len(scores) // 2
        if mid > 0:
            first_half = sum(scores[:mid]) / mid
            second_half = sum(scores[mid:]) / (len(scores) - mid)
            if second_half > first_half * 1.05:
                trend_dir = "increasing"
            elif second_half < first_half * 0.95:
                trend_dir = "decreasing"
            else:
                trend_dir = "stable"
        else:
            trend_dir = "stable"

        stats = {
            "average": round(avg_score, 2),
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "trend": trend_dir,
        }
    else:
        stats = {"average": 0, "min": 0, "max": 0, "trend": "stable"}

    return {
        "airport_code": airport_code or "ALL",
        "category": category or "total",
        "period": period,
        "data": trend_data,
        "statistics": stats,
    }


@router.get("/time-series", response_model=TimeSeriesResponse)
async def get_time_series(
    period: str = "1M",
    airport_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """시계열 데이터 조회 (종합+카테고리별)"""
    service = AnalyticsService(db)
    data = await service.get_time_series(period=period, airport_code=airport_code)
    return {"data": data}


@router.get("/correlation-matrix", response_model=CorrelationMatrixResponse)
async def get_correlation_matrix(db: AsyncSession = Depends(get_db)):
    """카테고리 간 상관관계 행렬"""
    service = AnalyticsService(db)
    result = await service.get_correlation_matrix()
    return result


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(db: AsyncSession = Depends(get_db)):
    """전체 통계"""
    # 전체 데이터 건수
    count_stmt = select(func.count(RiskAssessment.id))
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # 날짜 범위
    date_stmt = select(
        func.min(RiskAssessment.assessed_date),
        func.max(RiskAssessment.assessed_date),
    )
    date_result = (await db.execute(date_stmt)).one()
    start_date = str(date_result[0]) if date_result[0] else ""
    end_date = str(date_result[1]) if date_result[1] else ""

    # HIGH/CRITICAL 건수
    high_risk_stmt = select(func.count(RiskAssessment.id)).where(
        RiskAssessment.risk_level.in_(["HIGH", "CRITICAL"])
    )
    high_risk_count = (await db.execute(high_risk_stmt)).scalar() or 0

    # 카테고리별 통계
    cat_stmt = select(
        CategoryScoreRecord.category_code,
        func.count(CategoryScoreRecord.id),
        func.avg(CategoryScoreRecord.score),
    ).group_by(CategoryScoreRecord.category_code)
    cat_rows = (await db.execute(cat_stmt)).all()

    by_category = {}
    for row in cat_rows:
        by_category[row[0]] = {
            "incidents": int(row[1]),
            "avg_severity": round(float(row[2]), 1) if row[2] else 0,
        }

    # 공항별 통계
    airport_stmt2 = select(
        RiskAssessment.airport_code,
        func.count(RiskAssessment.id).label("total"),
    ).group_by(RiskAssessment.airport_code)
    airport_rows = (await db.execute(airport_stmt2)).all()

    # 공항별 high-risk 건수 별도 쿼리
    airport_risk_stmt = (
        select(
            RiskAssessment.airport_code,
            func.count(RiskAssessment.id).label("risk_days"),
        )
        .where(RiskAssessment.risk_level.in_(["HIGH", "CRITICAL"]))
        .group_by(RiskAssessment.airport_code)
    )
    risk_rows = (await db.execute(airport_risk_stmt)).all()
    risk_map = {r[0]: r[1] for r in risk_rows}

    by_airport = {}
    for row in airport_rows:
        by_airport[row[0]] = {
            "incidents": int(row[1]),
            "risk_days": risk_map.get(row[0], 0),
        }

    return {
        "overview": {
            "total_data_points": total_count,
            "analysis_start_date": start_date,
            "last_incident_date": end_date,
            "total_incidents": high_risk_count,
        },
        "by_category": by_category,
        "by_airport": by_airport,
        "updated_at": datetime.now().isoformat(),
    }
