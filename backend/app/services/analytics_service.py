"""
고급 분석 서비스 — 시계열, 상관관계 행렬
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_history import CategoryScoreRecord, RiskAssessment

logger = logging.getLogger(__name__)

CATEGORIES = ["weather", "aviation", "security", "health", "operational", "external"]


class AnalyticsService:
    """분석 쿼리 서비스"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── 시계열 데이터 ─────────────────────────────

    async def get_time_series(
        self,
        period: str = "1M",
        airport_code: Optional[str] = None,
    ) -> List[dict]:
        """날짜별 종합/카테고리 점수 시계열 반환"""
        period_days = {"1W": 7, "1M": 30, "3M": 90, "6M": 180}
        days = period_days.get(period, 30)
        cutoff = datetime.now().date() - timedelta(days=days)

        # 종합 점수 쿼리
        total_stmt = (
            select(
                RiskAssessment.assessed_date,
                func.avg(RiskAssessment.total_score).label("total_score"),
            )
            .where(RiskAssessment.assessed_date >= cutoff)
            .group_by(RiskAssessment.assessed_date)
            .order_by(RiskAssessment.assessed_date)
        )

        if airport_code:
            total_stmt = total_stmt.where(
                RiskAssessment.airport_code == airport_code
            )

        total_result = await self.session.execute(total_stmt)
        total_rows = total_result.all()

        # 카테고리별 점수 쿼리
        cat_stmt = (
            select(
                RiskAssessment.assessed_date,
                CategoryScoreRecord.category_code,
                func.avg(CategoryScoreRecord.score).label("avg_score"),
            )
            .join(
                CategoryScoreRecord,
                CategoryScoreRecord.assessment_id == RiskAssessment.id,
            )
            .where(RiskAssessment.assessed_date >= cutoff)
            .group_by(
                RiskAssessment.assessed_date,
                CategoryScoreRecord.category_code,
            )
            .order_by(RiskAssessment.assessed_date)
        )

        if airport_code:
            cat_stmt = cat_stmt.where(
                RiskAssessment.airport_code == airport_code
            )

        cat_result = await self.session.execute(cat_stmt)
        cat_rows = cat_result.all()

        # 날짜별로 합치기
        date_map: Dict[str, dict] = {}
        for row in total_rows:
            d = str(row.assessed_date)
            date_map[d] = {
                "date": d,
                "total_score": round(float(row.total_score), 1),
                "categories": {},
            }

        for row in cat_rows:
            d = str(row.assessed_date)
            if d in date_map:
                date_map[d]["categories"][row.category_code] = round(
                    float(row.avg_score), 1
                )

        return list(date_map.values())

    # ── 상관관계 행렬 ─────────────────────────────

    async def get_correlation_matrix(self) -> dict:
        """카테고리 간 상관관계 행렬 계산 (피어슨 상관계수)"""
        # 최근 90일 데이터
        cutoff = datetime.now().date() - timedelta(days=90)

        stmt = (
            select(
                RiskAssessment.assessed_date,
                RiskAssessment.airport_code,
                CategoryScoreRecord.category_code,
                CategoryScoreRecord.score,
            )
            .join(
                CategoryScoreRecord,
                CategoryScoreRecord.assessment_id == RiskAssessment.id,
            )
            .where(RiskAssessment.assessed_date >= cutoff)
            .order_by(RiskAssessment.assessed_date)
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        if len(rows) < 10:
            return {"categories": [], "matrix": []}

        # (date, airport) 키로 카테고리별 점수 벡터 구성
        data_points: Dict[str, Dict[str, List[float]]] = {}
        for row in rows:
            key = f"{row.assessed_date}_{row.airport_code}"
            if key not in data_points:
                data_points[key] = {}
            data_points[key][row.category_code] = float(row.score)

        # 카테고리별 점수 벡터 추출
        present_cats = set()
        for scores in data_points.values():
            present_cats.update(scores.keys())

        categories = [c for c in CATEGORIES if c in present_cats]
        if len(categories) < 2:
            return {"categories": [], "matrix": []}

        vectors: Dict[str, List[float]] = {c: [] for c in categories}
        for scores in data_points.values():
            if all(c in scores for c in categories):
                for c in categories:
                    vectors[c].append(scores[c])

        n = len(vectors[categories[0]])
        if n < 5:
            return {"categories": categories, "matrix": _identity_matrix(len(categories))}

        # 피어슨 상관계수 행렬 계산
        matrix = []
        for i, ci in enumerate(categories):
            row = []
            for j, cj in enumerate(categories):
                if i == j:
                    row.append(1.0)
                else:
                    r = _pearson(vectors[ci], vectors[cj])
                    row.append(round(r, 2))
            matrix.append(row)

        return {"categories": categories, "matrix": matrix}


def _pearson(x: List[float], y: List[float]) -> float:
    """피어슨 상관계수 계산"""
    n = len(x)
    if n == 0:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    std_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    std_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

    if std_x == 0 or std_y == 0:
        return 0.0

    return cov / (std_x * std_y)


def _identity_matrix(size: int) -> List[List[float]]:
    """단위 행렬 생성"""
    return [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
