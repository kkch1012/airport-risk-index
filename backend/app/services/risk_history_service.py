"""
위험지수 이력 저장/조회 서비스
"""

import logging
from datetime import date
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_history import RiskAssessment, CategoryScoreRecord
from app.services.risk_calculator import RiskResult

logger = logging.getLogger(__name__)


class RiskHistoryService:
    """위험지수 DB 이력 관리"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_assessment(self, result: RiskResult) -> Optional[RiskAssessment]:
        """단건 저장 (upsert: 같은 날 같은 공항이면 업데이트)"""
        assessed_date = date.fromisoformat(result.date)

        # 기존 레코드 조회
        stmt = select(RiskAssessment).where(
            and_(
                RiskAssessment.airport_code == result.airport_code,
                RiskAssessment.assessed_date == assessed_date,
            )
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()

        if existing:
            # 업데이트
            existing.total_score = result.total_score
            existing.risk_level = result.risk_level
            existing.airport_name = result.airport_name

            # 기존 카테고리 점수 삭제 후 재생성
            await self.session.execute(
                CategoryScoreRecord.__table__.delete().where(
                    CategoryScoreRecord.assessment_id == existing.id
                )
            )
            for cat_code, cat_score in result.categories.items():
                record = CategoryScoreRecord(
                    assessment_id=existing.id,
                    category_code=cat_code,
                    category_name=cat_score.name,
                    score=cat_score.score,
                    level=cat_score.level,
                    factors=cat_score.factors,
                )
                self.session.add(record)

            assessment = existing
        else:
            # 신규 생성
            assessment = RiskAssessment(
                airport_code=result.airport_code,
                airport_name=result.airport_name,
                assessed_date=assessed_date,
                total_score=result.total_score,
                risk_level=result.risk_level,
            )
            self.session.add(assessment)
            await self.session.flush()  # id 확보

            for cat_code, cat_score in result.categories.items():
                record = CategoryScoreRecord(
                    assessment_id=assessment.id,
                    category_code=cat_code,
                    category_name=cat_score.name,
                    score=cat_score.score,
                    level=cat_score.level,
                    factors=cat_score.factors,
                )
                self.session.add(record)

        await self.session.commit()
        return assessment

    async def save_batch(self, results: List[RiskResult]) -> int:
        """여러 공항 일괄 저장. 저장 성공 건수 반환."""
        saved = 0
        for result in results:
            try:
                await self.save_assessment(result)
                saved += 1
            except Exception:
                logger.exception(
                    "Failed to save assessment for %s", result.airport_code
                )
                await self.session.rollback()
        return saved

    async def get_history(
        self,
        airport_code: str,
        start_date: date,
        end_date: date,
        limit: int = 0,
        offset: int = 0,
    ) -> List[RiskAssessment]:
        """기간별 이력 조회 (페이지네이션 지원)"""
        stmt = (
            select(RiskAssessment)
            .where(
                and_(
                    RiskAssessment.airport_code == airport_code,
                    RiskAssessment.assessed_date >= start_date,
                    RiskAssessment.assessed_date <= end_date,
                )
            )
            .order_by(RiskAssessment.assessed_date)
        )
        if offset > 0:
            stmt = stmt.offset(offset)
        if limit > 0:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_history_count(
        self,
        airport_code: str,
        start_date: date,
        end_date: date,
    ) -> int:
        """기간별 이력 건수 조회"""
        from sqlalchemy import func as sa_func

        stmt = (
            select(sa_func.count(RiskAssessment.id))
            .where(
                and_(
                    RiskAssessment.airport_code == airport_code,
                    RiskAssessment.assessed_date >= start_date,
                    RiskAssessment.assessed_date <= end_date,
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_latest(self, airport_code: str) -> Optional[RiskAssessment]:
        """특정 공항의 최신 평가 조회"""
        stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.airport_code == airport_code)
            .order_by(RiskAssessment.assessed_date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
