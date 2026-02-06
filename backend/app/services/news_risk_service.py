"""
뉴스 위험 집계 서비스
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class NewsRiskService:
    """뉴스 데이터 기반 위험 집계"""

    def calculate_news_risk(
        self, articles: List[Dict], hours: int = 24
    ) -> Dict[str, float]:
        """
        카테고리별 뉴스 위험 점수 집계

        Returns:
            {"weather": 35.0, "security": 10.0, ...}
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        category_scores: Dict[str, List[float]] = {}

        for article in articles:
            # 시간 필터
            pub_at = article.get("published_at", "")
            if pub_at:
                try:
                    pub_dt = datetime.fromisoformat(pub_at)
                    if pub_dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            category = article.get("category", "general")
            score = article.get("risk_score", 0)
            if score > 0 and category != "general":
                category_scores.setdefault(category, []).append(score)

        # 카테고리별 평균 점수
        result = {}
        for category, scores in category_scores.items():
            if scores:
                # 최대값 60% + 평균 40%
                result[category] = round(
                    max(scores) * 0.6 + sum(scores) / len(scores) * 0.4, 1
                )

        return result

    def get_trending_risks(
        self, articles: List[Dict], hours: int = 24
    ) -> List[Dict]:
        """
        최근 고위험 뉴스 트렌드

        Returns:
            [{"category": "weather", "article_count": 5, "avg_score": 45.0, "top_article": {...}}, ...]
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        categories: Dict[str, List[Dict]] = {}

        for article in articles:
            pub_at = article.get("published_at", "")
            if pub_at:
                try:
                    pub_dt = datetime.fromisoformat(pub_at)
                    if pub_dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            cat = article.get("category", "general")
            if cat != "general":
                categories.setdefault(cat, []).append(article)

        trends = []
        for category, cat_articles in categories.items():
            scores = [a.get("risk_score", 0) for a in cat_articles]
            top = max(cat_articles, key=lambda x: x.get("risk_score", 0))
            trends.append({
                "category": category,
                "article_count": len(cat_articles),
                "avg_score": round(sum(scores) / len(scores), 1),
                "max_score": max(scores),
                "top_article": {
                    "title": top.get("title", ""),
                    "url": top.get("url", ""),
                    "risk_score": top.get("risk_score", 0),
                },
            })

        trends.sort(key=lambda x: x["max_score"], reverse=True)
        return trends
