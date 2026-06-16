"""
데이터 수집기 테스트
"""

import pytest
from app.collectors.weather import WeatherCollector
from app.collectors.aviation_safety import AviationSafetyCollector
from app.collectors.flight_status import FlightStatusCollector
from app.collectors.health_risk import HealthRiskCollector
from app.collectors.travel_advisory import TravelAdvisoryCollector


class TestWeatherCollector:
    """기상 수집기 테스트"""

    @pytest.fixture
    def collector(self):
        return WeatherCollector()

    def test_initialization(self, collector):
        """초기화 확인"""
        assert collector.name == "weather"
        assert collector.source_name == "기상청"

    def test_airport_grids(self, collector):
        """공항 격자 좌표 데이터 확인"""
        assert hasattr(collector, 'AIRPORT_GRIDS')
        assert "ICN" in collector.AIRPORT_GRIDS
        assert "GMP" in collector.AIRPORT_GRIDS
        # 좌표 데이터 구조 확인
        icn = collector.AIRPORT_GRIDS["ICN"]
        assert "nx" in icn
        assert "ny" in icn
        assert "name" in icn

    def test_category_mapping(self, collector):
        """기상 카테고리 매핑 확인"""
        assert hasattr(collector, 'CATEGORY_MAP')
        assert "T1H" in collector.CATEGORY_MAP  # 기온
        assert "WSD" in collector.CATEGORY_MAP  # 풍속
        assert "RN1" in collector.CATEGORY_MAP  # 강수량

    def test_precipitation_type_mapping(self, collector):
        """강수형태 매핑 확인"""
        assert hasattr(collector, 'PTY_MAP')
        assert collector.PTY_MAP["0"] == "없음"
        assert collector.PTY_MAP["3"] == "눈"


class TestAviationSafetyCollector:
    """항공안전 수집기 테스트"""

    @pytest.fixture
    def collector(self):
        return AviationSafetyCollector()

    def test_initialization(self, collector):
        """초기화 확인"""
        assert collector.name == "aviation_safety"

    @pytest.mark.asyncio
    async def test_collect_returns_list(self, collector):
        """수집 결과가 리스트인지 확인"""
        data = await collector.collect()
        assert isinstance(data, list)


class TestFlightStatusCollector:
    """운항정보 수집기 테스트"""

    @pytest.fixture
    def collector(self):
        return FlightStatusCollector()

    def test_initialization(self, collector):
        """초기화 확인"""
        assert collector.name == "flight_status"
        assert collector.source_name == "한국공항공사"

    def test_has_airport_mapping(self, collector):
        """공항 매핑 존재 확인"""
        # 공항 코드 관련 속성이 있는지 확인
        assert hasattr(collector, 'DOMESTIC_AIRPORTS')
        airports = collector.DOMESTIC_AIRPORTS
        assert "GMP" in airports  # 김포
        assert "PUS" in airports  # 김해


class TestHealthRiskCollector:
    """보건위험 수집기 테스트"""

    @pytest.fixture
    def collector(self):
        return HealthRiskCollector()

    def test_initialization(self, collector):
        """초기화 확인"""
        assert collector.name == "health_risk"
        assert collector.source_name == "질병관리청"

    @pytest.mark.asyncio
    async def test_collect_returns_data(self, collector):
        """수집 결과 반환 확인"""
        data = await collector.collect()
        assert data is not None


class TestTravelAdvisoryCollector:
    """여행경보 수집기 테스트"""

    @pytest.fixture
    def collector(self):
        return TravelAdvisoryCollector()

    def test_initialization(self, collector):
        """초기화 확인"""
        assert collector.name == "travel_advisory"
        assert collector.source_name == "외교부"

    def test_alarm_levels(self, collector):
        """경보 단계 매핑 확인"""
        levels = collector.ALARM_LEVELS
        assert "1" in levels
        assert "4" in levels
        # 4단계가 가장 높은 점수
        assert levels["4"]["score"] > levels["1"]["score"]
        assert levels["4"]["score"] == 100
        assert levels["1"]["score"] == 10

    def test_target_countries(self, collector):
        """대상 국가 목록 확인"""
        countries = collector.TARGET_COUNTRIES
        assert len(countries) >= 40  # 50개 가량의 국가
        assert "JP" in countries  # 일본
        assert "US" in countries  # 미국
        assert "CN" in countries  # 중국

    def test_continent_mapping(self, collector):
        """대륙 매핑 확인"""
        continent = collector._get_continent("JP")
        assert continent == "동북아시아"

        continent = collector._get_continent("US")
        assert continent == "북미"

        continent = collector._get_continent("DE")
        assert continent == "유럽"

    @pytest.mark.asyncio
    async def test_collect_returns_list(self, collector):
        """수집 결과가 리스트인지 확인"""
        data = await collector.collect()
        assert isinstance(data, list)

    def test_transform_data(self, collector):
        """데이터 변환 확인"""
        raw_data = {
            "country_code": "JP",
            "country_name": "일본",
            "alarm_lvl": "1",
            "collected_at": "2026-02-04T10:00:00",
        }
        transformed = collector.transform(raw_data)
        assert transformed["country_code"] == "JP"
        assert transformed["alarm_level"] == 1
        assert transformed["alarm_name"] == "여행유의"
        assert transformed["risk_score"] == 10

    def test_validate_data(self, collector):
        """데이터 유효성 검증 확인"""
        valid_data = {
            "country_code": "JP",
            "alarm_level": 1,
        }
        assert collector.validate(valid_data) is True

        invalid_data = {
            "country_code": "",
            "alarm_level": 1,
        }
        assert collector.validate(invalid_data) is False

    def test_get_summary(self, collector):
        """요약 통계 확인"""
        data_list = [
            {"country_code": "JP", "country_name": "일본", "alarm_level": 1, "risk_score": 10, "alarm_name": "여행유의"},
            {"country_code": "RU", "country_name": "러시아", "alarm_level": 3, "risk_score": 70, "alarm_name": "출국권고"},
        ]
        summary = collector.get_summary(data_list)
        assert summary["total_countries"] == 2
        assert summary["level_distribution"]["caution"] == 1
        assert summary["level_distribution"]["advisory"] == 1
        assert len(summary["high_risk_countries"]) == 1
