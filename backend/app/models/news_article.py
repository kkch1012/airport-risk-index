"""
뉴스 기사 데이터 모델
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text
from app.core.database import Base


class NewsArticle(Base):
    """뉴스 기사 기록"""

    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String(200), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    source = Column(String(100), nullable=True)
    category = Column(String(30), nullable=True, index=True)
    risk_score = Column(Float, nullable=True)
    keywords = Column(JSON, nullable=True)
    airport_code = Column(String(10), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<NewsArticle {self.article_id}: {self.title[:50]}>"
