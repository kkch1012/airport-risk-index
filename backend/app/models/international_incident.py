"""
해외 항공사고 데이터 모델
"""

from datetime import datetime, date as date_type

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text
from app.core.database import Base


class InternationalIncident(Base):
    """해외 항공사고/준사고 기록"""

    __tablename__ = "international_incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    link = Column(String(1000), nullable=True)
    country_code = Column(String(10), nullable=True, index=True)
    airport_code = Column(String(10), nullable=True, index=True)
    incident_date = Column(Date, nullable=True, index=True)
    severity = Column(String(20), nullable=True)
    risk_score = Column(Float, nullable=True)
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<InternationalIncident {self.incident_id}: {self.title[:50]}>"
