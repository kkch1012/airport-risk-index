"""
해외 데이터 수집기 테스트
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.collectors.international_weather import (
    InternationalWeatherCollector,
    INTERNATIONAL_AIRPORTS,
)
from app.collectors.international_aviation import (
    InternationalAviationCollector,
    MONITORED_COUNTRIES,
)


# ─── InternationalWeatherCollector 테스트 ──────────


class TestInternationalWeatherCollector:
    """해외 기상 수집기 테스트"""

    def test_initialization(self):
        collector = InternationalWeatherCollector()
        assert collector.name == "international_weather"
        assert collector.collection_interval == 3600

    @pytest.mark.asyncio
    async def test_collect_returns_data(self):
        """수집 결과가 리스트 반환"""
        async with InternationalWeatherCollector() as collector:
            data = await collector.collect()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_run_produces_transformed_data(self):
        """run()이 변환된 데이터 반환"""
        async with InternationalWeatherCollector() as collector:
            result = await collector.run()
        assert result["status"] == "success"
        assert result["transformed_count"] > 0

        # 변환된 데이터 구조 확인
        item = result["data"][0]
        assert "icao_code" in item
        assert "iata_code" in item
        assert "risk_score" in item
        assert "risk_factors" in item
        assert "wind" in item["risk_factors"]

    def test_wind_risk(self):
        """풍속 위험 점수"""
        collector = InternationalWeatherCollector()
        assert collector._wind_risk(5) == 20  # 약한 바람
        assert collector._wind_risk(20) == 40  # 중간풍
        assert collector._wind_risk(30) == 60  # 강풍
        assert collector._wind_risk(50) == 100  # 초강풍

    def test_visibility_risk(self):
        """시정 위험 점수"""
        collector = InternationalWeatherCollector()
        # 10 SM = ~16000m → 낮은 위험
        assert collector._visibility_risk(10) == 10
        # 1 SM = ~1600m → 높은 위험
        assert collector._visibility_risk(1) >= 30

    def test_weather_phenomena_risk(self):
        """기상현상 위험 점수"""
        collector = InternationalWeatherCollector()
        assert collector._weather_phenomena_risk("") == 0
        assert collector._weather_phenomena_risk("TS") == 70  # 뇌우
        assert collector._weather_phenomena_risk("FG") == 40  # 안개
        assert collector._weather_phenomena_risk("RA") == 20  # 비

    def test_statute_miles_to_meters(self):
        """마일 → 미터 변환"""
        assert abs(InternationalWeatherCollector._statute_miles_to_meters(1) - 1609.34) < 0.1

    def test_transform_mock_data(self):
        """목업 데이터 변환"""
        collector = InternationalWeatherCollector()
        mock_item = {
            "icaoId": "RJTT",
            "reportTime": "2026-02-06T12:00:00Z",
            "wspd": 15,
            "wgst": 25,
            "visib": 5,
            "temp": 10,
            "dewp": 5,
            "altim": 29.92,
            "wxString": "RA",
            "cover": "BKN",
        }
        result = collector.transform(mock_item)
        assert result["icao_code"] == "RJTT"
        assert result["iata_code"] == "HND"
        assert result["country_code"] == "JP"
        assert result["risk_score"] >= 0
        assert result["risk_score"] <= 100

    def test_get_country_weather_risk(self):
        """국가별 기상 위험 점수"""
        collector = InternationalWeatherCollector()
        data = [
            {"country_code": "JP", "risk_score": 30},
            {"country_code": "JP", "risk_score": 50},
            {"country_code": "CN", "risk_score": 20},
        ]
        assert collector.get_country_weather_risk(data, "JP") == 40.0
        assert collector.get_country_weather_risk(data, "CN") == 20.0
        assert collector.get_country_weather_risk(data, "US") == 0.0

    def test_international_airports_coverage(self):
        """주요 공항이 모두 포함되어 있는지"""
        assert "RJTT" in INTERNATIONAL_AIRPORTS  # 하네다
        assert "ZBAA" in INTERNATIONAL_AIRPORTS  # 베이징
        assert "KLAX" in INTERNATIONAL_AIRPORTS  # LA
        assert len(INTERNATIONAL_AIRPORTS) >= 10


# ─── InternationalAviationCollector 테스트 ──────────


class TestInternationalAviationCollector:
    """해외 항공사고 수집기 테스트"""

    def test_initialization(self):
        collector = InternationalAviationCollector()
        assert collector.name == "international_aviation"
        assert collector.collection_interval == 21600

    @pytest.mark.asyncio
    async def test_collect_returns_data(self):
        """수집 결과가 리스트 반환"""
        async with InternationalAviationCollector() as collector:
            data = await collector.collect()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_run_produces_transformed_data(self):
        """run()이 변환된 데이터 반환"""
        async with InternationalAviationCollector() as collector:
            result = await collector.run()
        assert result["status"] == "success"
        assert result["transformed_count"] > 0

        item = result["data"][0]
        assert "incident_id" in item
        assert "title" in item
        assert "risk_score" in item
        assert "severity" in item

    def test_calculate_severity(self):
        """심각도 계산"""
        collector = InternationalAviationCollector()
        assert collector._calculate_severity("fatal crash") >= 90
        assert collector._calculate_severity("incident report") >= 50
        assert collector._calculate_severity("runway excursion") >= 30
        assert collector._calculate_severity("normal flight") == 20  # 기본값

    def test_severity_label(self):
        """심각도 라벨"""
        collector = InternationalAviationCollector()
        assert collector._severity_label(100) == "fatal"
        assert collector._severity_label(60) == "serious"
        assert collector._severity_label(30) == "minor"

    def test_extract_country(self):
        """국가 추출"""
        collector = InternationalAviationCollector()
        assert collector._extract_country("crash in japan near tokyo") == "JP"
        assert collector._extract_country("incident in usa") == "US"
        assert collector._extract_country("unknown location") == ""

    def test_recency_factor(self):
        """최근도 가중치"""
        from datetime import datetime, timedelta
        collector = InternationalAviationCollector()
        today = datetime.now().strftime("%Y-%m-%d")
        assert collector._recency_factor(today) == 1.5  # 오늘
        old = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
        assert collector._recency_factor(old) == 0.7  # 120일 전

    def test_parse_html_invalid(self):
        """잘못된 HTML 처리"""
        collector = InternationalAviationCollector()
        result = collector._parse_html("not valid html")
        assert result == []

    def test_parse_html_valid(self):
        """유효한 HTML 파싱 (Aviation Herald 형식)"""
        collector = InternationalAviationCollector()
        html = """<html><body>
        <span class="headline_avherald">
          <a href="/h?article=12345&opt=0">ANA B789 at Tokyo on Feb 17th 2026, engine oil problem</a>
        </span>
        <span class="headline_avherald">
          <a href="/h?article=12346&opt=0">Short</a>
        </span>
        </body></html>"""
        items = collector._parse_html(html)
        assert len(items) == 1  # 두 번째는 title 20자 미만이라 제외
        assert "ANA B789" in items[0]["title"]
        assert "avherald.com" in items[0]["link"]
        assert items[0]["pub_date"] == "2026-02-17"

    def test_extract_date_from_title(self):
        """제목에서 날짜 추출"""
        collector = InternationalAviationCollector()
        assert collector._extract_date_from_title(
            "ANA B789 at Tokyo on Feb 17th 2026, engine oil problem"
        ) == "2026-02-17"
        assert collector._extract_date_from_title(
            "Some title on Jan 1st 2025, incident"
        ) == "2025-01-01"

    def test_monitored_countries(self):
        """모니터링 대상 국가"""
        assert "JP" in MONITORED_COUNTRIES
        assert "CN" in MONITORED_COUNTRIES
        assert "US" in MONITORED_COUNTRIES

    def test_get_country_risk_summary(self):
        """국가별 위험 요약"""
        collector = InternationalAviationCollector()
        data = [
            {"country_code": "JP", "risk_score": 40},
            {"country_code": "JP", "risk_score": 60},
            {"country_code": "CN", "risk_score": 30},
            {"country_code": "KR", "risk_score": 50},  # KR은 모니터링 대상 아님
        ]
        summary = collector.get_country_risk_summary(data)
        assert summary["JP"] == 50.0
        assert summary["CN"] == 30.0
        assert "KR" not in summary


# ─── API 엔드포인트 테스트 ──────────


class TestInternationalAPI:
    """해외 데이터 API 테스트"""

    def test_international_incidents_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/international/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert "incidents" in data
        assert "total" in data

    def test_international_weather_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/international/weather")
        assert resp.status_code == 200
        data = resp.json()
        assert "weather" in data
        assert "total" in data

    def test_international_summary_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/international/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "incidents" in data
        assert "weather" in data

    def test_incidents_filter_by_severity(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/international/incidents?severity=minor")
        assert resp.status_code == 200
