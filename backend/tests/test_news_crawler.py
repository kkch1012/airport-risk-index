"""
뉴스 크롤링 테스트
"""

import pytest
import pytest_asyncio

from app.collectors.news_crawler import (
    NewsCrawler,
    RISK_KEYWORDS,
    AIRPORT_KEYWORDS,
)
from app.services.news_risk_service import NewsRiskService


# ─── NewsCrawler 테스트 ─────────────────────


class TestNewsCrawler:
    """뉴스 크롤러 단위 테스트"""

    def test_initialization(self):
        crawler = NewsCrawler()
        assert crawler.name == "news_crawler"
        assert crawler.collection_interval == 3600

    def test_detect_category_weather(self):
        crawler = NewsCrawler()
        cat, kws = crawler._detect_category("인천공항 태풍으로 결항 속출")
        assert cat == "weather"
        assert "태풍" in kws

    def test_detect_category_security(self):
        crawler = NewsCrawler()
        cat, kws = crawler._detect_category("공항 보안 검색에서 폭발물 위협")
        assert cat == "security"
        assert "폭발" in kws or "위협" in kws

    def test_detect_category_operational(self):
        crawler = NewsCrawler()
        cat, kws = crawler._detect_category("김포공항 활주로 폐쇄로 대규모 지연")
        assert cat == "operational"
        assert "지연" in kws

    def test_detect_category_health(self):
        crawler = NewsCrawler()
        cat, kws = crawler._detect_category("코로나 변이 확산으로 검역 강화")
        assert cat == "health"

    def test_detect_category_aviation(self):
        crawler = NewsCrawler()
        cat, kws = crawler._detect_category("여객기 엔진고장으로 긴급착륙")
        assert cat == "aviation"

    def test_detect_category_no_match(self):
        crawler = NewsCrawler()
        cat, kws = crawler._detect_category("좋은 날씨입니다")
        assert kws == []

    def test_calculate_risk_score_basic(self):
        crawler = NewsCrawler()
        score = crawler._calculate_risk_score("태풍 안개", ["태풍", "안개"])
        assert score >= 40  # 2개 키워드

    def test_calculate_risk_score_urgent(self):
        crawler = NewsCrawler()
        score = crawler._calculate_risk_score("속보: 사고 발생 긴급", ["사고"])
        assert score > 50  # 긴급 키워드 보너스

    def test_calculate_risk_score_no_keywords(self):
        crawler = NewsCrawler()
        score = crawler._calculate_risk_score("평범한 뉴스", [])
        assert score == 0

    def test_detect_airport(self):
        crawler = NewsCrawler()
        assert crawler._detect_airport("인천공항에서 사고 발생") == "ICN"
        assert crawler._detect_airport("김해공항 결항") == "PUS"
        assert crawler._detect_airport("뉴스 기사") is None

    def test_parse_rss_valid(self):
        crawler = NewsCrawler()
        xml = """<?xml version="1.0"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>인천공항 태풍으로 결항</title>
              <link>https://example.com/1</link>
              <pubDate>Thu, 06 Feb 2026 12:00:00 GMT</pubDate>
              <source>연합뉴스</source>
            </item>
          </channel>
        </rss>"""
        items = crawler._parse_rss(xml)
        assert len(items) == 1
        assert "태풍" in items[0]["title"]

    def test_parse_rss_invalid(self):
        crawler = NewsCrawler()
        assert crawler._parse_rss("invalid") == []

    @pytest.mark.asyncio
    async def test_collect_returns_data(self):
        """수집 결과 반환 (목업 포함)"""
        async with NewsCrawler() as crawler:
            data = await crawler.collect()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_run_produces_transformed_data(self):
        """run()이 변환/필터된 데이터 반환"""
        async with NewsCrawler() as crawler:
            result = await crawler.run()
        assert result["status"] == "success"

        # validate()가 키워드 있는 뉴스만 통과시킴
        for item in result["data"]:
            assert len(item.get("keywords", [])) > 0
            assert item.get("risk_score", 0) > 0

    def test_generate_id_consistency(self):
        crawler = NewsCrawler()
        data = {"title": "test", "link": "https://example.com"}
        id1 = crawler._generate_id(data)
        id2 = crawler._generate_id(data)
        assert id1 == id2

    def test_risk_keywords_coverage(self):
        """모든 위험 카테고리에 키워드가 있는지"""
        for category in ["weather", "security", "operational", "health", "aviation"]:
            assert category in RISK_KEYWORDS
            assert len(RISK_KEYWORDS[category]) > 0

    def test_airport_keywords_coverage(self):
        """주요 공항이 키워드에 포함되어 있는지"""
        codes = set(AIRPORT_KEYWORDS.values())
        assert "ICN" in codes
        assert "GMP" in codes
        assert "PUS" in codes
        assert "CJU" in codes


# ─── NewsRiskService 테스트 ─────────────────


class TestNewsRiskService:
    """뉴스 위험 서비스 테스트"""

    def test_calculate_news_risk(self):
        service = NewsRiskService()
        articles = [
            {"category": "weather", "risk_score": 50, "published_at": ""},
            {"category": "weather", "risk_score": 30, "published_at": ""},
            {"category": "security", "risk_score": 70, "published_at": ""},
        ]
        result = service.calculate_news_risk(articles)
        assert "weather" in result
        assert "security" in result
        assert result["weather"] > 0
        assert result["security"] > 0

    def test_calculate_news_risk_empty(self):
        service = NewsRiskService()
        result = service.calculate_news_risk([])
        assert result == {}

    def test_get_trending_risks(self):
        service = NewsRiskService()
        articles = [
            {"category": "aviation", "risk_score": 80, "title": "사고", "url": "", "published_at": ""},
            {"category": "aviation", "risk_score": 40, "title": "결함", "url": "", "published_at": ""},
            {"category": "weather", "risk_score": 30, "title": "태풍", "url": "", "published_at": ""},
        ]
        trends = service.get_trending_risks(articles)
        assert len(trends) >= 1
        # 가장 위험한 카테고리가 첫 번째
        assert trends[0]["category"] == "aviation"
        assert trends[0]["article_count"] == 2

    def test_general_category_excluded(self):
        service = NewsRiskService()
        articles = [
            {"category": "general", "risk_score": 50, "published_at": ""},
        ]
        result = service.calculate_news_risk(articles)
        assert "general" not in result


# ─── API 엔드포인트 테스트 ──────────────────


class TestNewsAPI:
    """뉴스 API 테스트"""

    def test_recent_news_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/news/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert "articles" in data
        assert "total" in data

    def test_trending_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/news/trending")
        assert resp.status_code == 200
        data = resp.json()
        assert "trends" in data
        assert "category_scores" in data

    def test_recent_news_category_filter(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/news/recent?category=weather")
        assert resp.status_code == 200
