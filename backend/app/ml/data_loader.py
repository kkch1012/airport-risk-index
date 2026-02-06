"""
DB에서 분석용 DataFrame을 추출하는 데이터 로더
"""

import logging
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_history import CategoryScoreRecord, RiskAssessment

logger = logging.getLogger(__name__)

CATEGORY_CODES = ["weather", "aviation", "security", "health", "operational", "external"]


class AnalysisDataLoader:
    """DB 이력 데이터를 pandas DataFrame으로 로드"""

    MIN_DATA_POINTS = 30

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_data_point_count(self) -> int:
        """RiskAssessment 총 건수"""
        stmt = select(func.count(RiskAssessment.id))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def has_sufficient_data(self) -> bool:
        """최소 데이터포인트 확인"""
        count = await self.get_data_point_count()
        return count >= self.MIN_DATA_POINTS

    async def load_category_scores(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        airport_codes: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        카테고리 점수를 wide-format DataFrame으로 반환.

        Columns: assessed_date, airport_code, total_score, risk_level,
                 weather, aviation, security, health, operational, external
        """
        stmt = (
            select(
                RiskAssessment.assessed_date,
                RiskAssessment.airport_code,
                RiskAssessment.total_score,
                RiskAssessment.risk_level,
                CategoryScoreRecord.category_code,
                CategoryScoreRecord.score,
            )
            .join(
                CategoryScoreRecord,
                CategoryScoreRecord.assessment_id == RiskAssessment.id,
            )
        )

        if start_date:
            stmt = stmt.where(RiskAssessment.assessed_date >= start_date)
        if end_date:
            stmt = stmt.where(RiskAssessment.assessed_date <= end_date)
        if airport_codes:
            stmt = stmt.where(RiskAssessment.airport_code.in_(airport_codes))

        stmt = stmt.order_by(RiskAssessment.assessed_date)
        result = await self.session.execute(stmt)
        rows = result.all()

        if not rows:
            return pd.DataFrame(
                columns=["assessed_date", "airport_code", "total_score", "risk_level"]
                + CATEGORY_CODES
            )

        # Long → wide pivot
        data = []
        for row in rows:
            data.append({
                "assessed_date": row.assessed_date,
                "airport_code": row.airport_code,
                "total_score": row.total_score,
                "risk_level": row.risk_level,
                "category_code": row.category_code,
                "score": row.score,
            })

        long_df = pd.DataFrame(data)
        pivot = long_df.pivot_table(
            index=["assessed_date", "airport_code", "total_score", "risk_level"],
            columns="category_code",
            values="score",
            aggfunc="first",
        ).reset_index()

        # 누락 카테고리 컬럼 채우기
        for cat in CATEGORY_CODES:
            if cat not in pivot.columns:
                pivot[cat] = 0.0

        return pivot

    async def load_factor_details(
        self,
        category_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        특정 카테고리의 sub-factor JSON을 컬럼으로 전개.
        """
        stmt = (
            select(
                RiskAssessment.assessed_date,
                RiskAssessment.airport_code,
                CategoryScoreRecord.factors,
            )
            .join(
                CategoryScoreRecord,
                CategoryScoreRecord.assessment_id == RiskAssessment.id,
            )
            .where(CategoryScoreRecord.category_code == category_code)
        )

        if start_date:
            stmt = stmt.where(RiskAssessment.assessed_date >= start_date)
        if end_date:
            stmt = stmt.where(RiskAssessment.assessed_date <= end_date)

        result = await self.session.execute(stmt)
        rows = result.all()

        if not rows:
            return pd.DataFrame()

        records = []
        for row in rows:
            record = {
                "assessed_date": row.assessed_date,
                "airport_code": row.airport_code,
            }
            if row.factors and isinstance(row.factors, dict):
                record.update(row.factors)
            records.append(record)

        return pd.DataFrame(records)
