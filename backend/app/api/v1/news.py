"""
뉴스 크롤링 API 엔드포인트
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/recent")
async def get_recent_news(
    category: Optional[str] = Query(None, description="카테고리 필터"),
    airport_code: Optional[str] = Query(None, description="공항 코드 필터"),
    hours: int = Query(24, ge=1, le=168, description="시간 범위 (최대 7일)"),
    limit: int = Query(20, ge=1, le=100),
):
    """최근 위험 관련 뉴스 조회"""
    from app.collectors.news_crawler import NewsCrawler

    async with NewsCrawler() as crawler:
        result = await crawler.run()

    if result["status"] != "success":
        return {"articles": [], "total": 0}

    articles = result["data"]

    # 필터링
    if category:
        articles = [a for a in articles if a.get("category") == category]
    if airport_code:
        articles = [a for a in articles if a.get("airport_code") == airport_code.upper()]

    # 정렬 (위험도 높은 순)
    articles.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    articles = articles[:limit]

    return {
        "articles": articles,
        "total": len(articles),
        "hours": hours,
    }


@router.get("/trending")
async def get_trending_risks(
    hours: int = Query(24, ge=1, le=168),
):
    """뉴스 기반 위험 트렌드"""
    from app.collectors.news_crawler import NewsCrawler
    from app.services.news_risk_service import NewsRiskService

    async with NewsCrawler() as crawler:
        result = await crawler.run()

    if result["status"] != "success":
        return {"trends": [], "category_scores": {}}

    articles = result["data"]
    service = NewsRiskService()

    return {
        "trends": service.get_trending_risks(articles, hours=hours),
        "category_scores": service.calculate_news_risk(articles, hours=hours),
    }
