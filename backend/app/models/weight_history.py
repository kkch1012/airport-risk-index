"""
가중치 이력 ORM 모델
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    JSON,
    String,
)

from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class WeightHistory(Base):
    """카테고리 가중치 산출 이력"""

    __tablename__ = "weight_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    calculated_at = Column(DateTime, nullable=False, default=_utcnow)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    method = Column(String(30), nullable=False)  # ensemble, correlation, regression, rf, variance
    category_weights = Column(JSON, nullable=False)  # {"weather": 0.20, ...}
    factor_weights = Column(JSON, nullable=True)
    metadata_info = Column(JSON, nullable=True)  # 분석 메타데이터
    sample_size = Column(Integer, nullable=False)
    analysis_period_start = Column(Date, nullable=True)
    analysis_period_end = Column(Date, nullable=True)

    def __repr__(self):
        return f"<WeightHistory {self.method} active={self.is_active} at={self.calculated_at}>"
