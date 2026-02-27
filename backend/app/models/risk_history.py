"""
위험지수 이력 ORM 모델
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class RiskAssessment(Base):
    """공항별 일자별 종합 위험지수 평가"""

    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    airport_code = Column(String(10), nullable=False, index=True)
    airport_name = Column(String(50), nullable=False)
    assessed_date = Column(Date, nullable=False, index=True)
    total_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # 카테고리별 점수 (1:N)
    category_scores = relationship(
        "CategoryScoreRecord",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("airport_code", "assessed_date", name="uq_airport_date"),
    )

    def __repr__(self):
        return f"<RiskAssessment {self.airport_code} {self.assessed_date} score={self.total_score}>"


class CategoryScoreRecord(Base):
    """카테고리별 위험 점수 기록"""

    __tablename__ = "category_score_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(
        Integer, ForeignKey("risk_assessments.id", ondelete="CASCADE"), nullable=False
    )
    category_code = Column(String(30), nullable=False)
    category_name = Column(String(50), nullable=False)
    score = Column(Float, nullable=False)
    level = Column(String(20), nullable=False)
    factors = Column(JSON, nullable=True)

    assessment = relationship("RiskAssessment", back_populates="category_scores")

    def __repr__(self):
        return f"<CategoryScoreRecord {self.category_code} score={self.score}>"
