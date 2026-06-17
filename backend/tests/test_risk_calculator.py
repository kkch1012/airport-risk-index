"""
위험지수 계산기 테스트
"""

import pytest
from app.services.risk_calculator import RiskCalculator, CategoryScore


class TestRiskCalculator:
    """RiskCalculator 클래스 테스트"""

    @pytest.fixture
    def calculator(self):
        """RiskCalculator 인스턴스"""
        return RiskCalculator()

    def test_calculator_initialization(self, calculator):
        """계산기 초기화 확인"""
        assert calculator is not None
        assert hasattr(calculator, 'CATEGORY_WEIGHTS')

    def test_category_weights_sum_to_one(self, calculator):
        """카테고리 가중치 합이 1인지 확인"""
        weights = calculator.CATEGORY_WEIGHTS
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_risk_level_boundaries(self, calculator):
        """위험등급 경계값 테스트"""
        # LOW: 0-25
        assert calculator._get_risk_level(0) == "LOW"
        assert calculator._get_risk_level(24.9) == "LOW"

        # MODERATE: 25-50
        assert calculator._get_risk_level(25) == "MODERATE"
        assert calculator._get_risk_level(49.9) == "MODERATE"

        # HIGH: 50-75
        assert calculator._get_risk_level(50) == "HIGH"
        assert calculator._get_risk_level(74.9) == "HIGH"

        # CRITICAL: 75-100
        assert calculator._get_risk_level(75) == "CRITICAL"
        assert calculator._get_risk_level(100) == "CRITICAL"

    def test_normalize_value(self, calculator):
        """값 정규화 테스트"""
        # 최소값 -> 0점
        assert calculator._normalize_value(0, 0, 100) == 0
        # 최대값 -> 100점
        assert calculator._normalize_value(100, 0, 100) == 100
        # 중간값 -> 50점
        assert calculator._normalize_value(50, 0, 100) == 50
        # 범위 밖 -> 클리핑
        assert calculator._normalize_value(150, 0, 100) == 100
        assert calculator._normalize_value(-10, 0, 100) == 0


class TestWeatherScore:
    """기상위험 점수 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RiskCalculator()

    def test_calm_weather_low_score(self, calculator):
        """평온한 기상 조건에서 낮은 점수"""
        weather_data = {
            "wind_speed": 2.0,  # 약한 바람
            "precipitation_1h": 0,  # 강수 없음
            "humidity": 50,  # 적정 습도
            "precipitation_type": 0,  # 강수 없음
        }
        result = calculator.calculate_weather_score(weather_data)
        assert isinstance(result, CategoryScore)
        assert result.score < 30, f"Calm weather should have low score, got {result.score}"

    def test_severe_weather_high_score(self, calculator):
        """악천후에서 높은 점수"""
        weather_data = {
            "wind_speed": 18.0,  # 강풍
            "precipitation_1h": 25.0,  # 많은 강수
            "humidity": 95,  # 높은 습도
            "precipitation_type": 3,  # 눈
        }
        result = calculator.calculate_weather_score(weather_data)
        assert result.score > 50, f"Severe weather should have high score, got {result.score}"

    def test_weather_score_range(self, calculator):
        """기상 점수가 0-100 범위인지 확인"""
        weather_data = {
            "wind_speed": 10.0,
            "precipitation_1h": 5.0,
            "humidity": 70,
            "precipitation_type": 1,
        }
        result = calculator.calculate_weather_score(weather_data)
        assert 0 <= result.score <= 100


class TestOperationalScore:
    """운영위험 점수 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RiskCalculator()

    def test_normal_operations_low_score(self, calculator):
        """정상 운영 시 낮은 점수"""
        ops_data = [{
            "airport_code": "ICN",
            "delay_rate": 5.0,  # 5% 지연율
            "cancellation_rate": 0.5,  # 0.5% 결항율
            "total_flights": 80,  # 적당한 운항편수
        }]
        result = calculator.calculate_operational_score("ICN", ops_data)
        assert isinstance(result, CategoryScore)
        assert result.score < 40, f"Normal operations should have low score, got {result.score}"

    def test_disrupted_operations_high_score(self, calculator):
        """운영 혼란 시 높은 점수"""
        ops_data = [{
            "airport_code": "ICN",
            "delay_rate": 25.0,  # 25% 지연율
            "cancellation_rate": 6.0,  # 6% 결항율
            "total_flights": 250,  # 많은 운항편수
        }]
        result = calculator.calculate_operational_score("ICN", ops_data)
        assert result.score > 60, f"Disrupted operations should have high score, got {result.score}"

    def test_missing_airport_data(self, calculator):
        """공항 데이터 없을 때 기본값"""
        result = calculator.calculate_operational_score("XXX", [])
        assert result.score == 10.0  # 기본 낮은 위험도
        assert result.has_data is False  # 데이터 없음 → 가중치 제외
        assert result.is_proxy is False

    def test_proxy_flag_propagates(self, calculator):
        """뉴스 프록시 운항 데이터는 is_proxy=True로 표시"""
        ops_data = [{
            "airport_code": "ICN",
            "delay_rate": 8.0,
            "cancellation_rate": 2.0,
            "total_flights": 0,
            "is_proxy": True,
        }]
        result = calculator.calculate_operational_score("ICN", ops_data)
        assert result.is_proxy is True
        assert result.has_data is True

    def test_real_data_not_proxy(self, calculator):
        """실측 운항 데이터는 is_proxy=False"""
        ops_data = [{
            "airport_code": "ICN",
            "delay_rate": 8.0,
            "cancellation_rate": 2.0,
            "total_flights": 100,
        }]
        result = calculator.calculate_operational_score("ICN", ops_data)
        assert result.is_proxy is False

    def test_proxy_score_capped(self, calculator):
        """추정치는 보수적 상한(40, MODERATE)으로 제한 — HIGH로 안 튐"""
        # 실측이면 62.5 나올 입력이지만 is_proxy면 40으로 캡
        proxy = [{
            "airport_code": "TAE", "delay_rate": 25.0,
            "cancellation_rate": 0.0, "is_proxy": True,
        }]
        result = calculator.calculate_operational_score("TAE", proxy)
        assert result.is_proxy is True
        assert result.score == 40.0
        assert result.level in ("LOW", "MODERATE")  # HIGH 아님

    def test_real_data_not_capped(self, calculator):
        """실측 데이터는 상한 적용 안 됨 (높으면 높게)"""
        real = [{
            "airport_code": "ICN", "delay_rate": 25.0,
            "cancellation_rate": 6.0, "total_flights": 200,
        }]
        result = calculator.calculate_operational_score("ICN", real)
        assert result.is_proxy is False
        assert result.score > 40  # 캡 없음


class TestExternalScore:
    """외부요인 점수 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RiskCalculator()

    def test_no_advisory_low_score(self, calculator):
        """여행경보 없을 때 낮은 점수"""
        advisory_data = [
            {"country_code": "JP", "risk_score": 0, "country_name": "일본"},
            {"country_code": "CN", "risk_score": 0, "country_name": "중국"},
        ]
        result = calculator.calculate_external_score("GMP", advisory_data)
        assert result.score < 20

    def test_high_advisory_high_score(self, calculator):
        """고위험 여행경보 시 높은 점수"""
        advisory_data = [
            {"country_code": "JP", "risk_score": 70, "country_name": "일본", "alarm_name": "출국권고"},
            {"country_code": "CN", "risk_score": 40, "country_name": "중국", "alarm_name": "여행자제"},
        ]
        result = calculator.calculate_external_score("GMP", advisory_data)
        assert result.score > 30

    def test_domestic_airport_low_score(self, calculator):
        """국내선 전용 공항은 낮은 점수"""
        result = calculator.calculate_external_score("KWJ", [])  # 광주 - 국제선 없음
        assert result.score == 5.0

    def test_external_proxy_flag(self, calculator):
        """매칭된 여행경보가 뉴스 프록시면 is_proxy=True"""
        advisory_data = [
            {"country_code": "JP", "risk_score": 40, "country_name": "일본", "is_proxy": True},
        ]
        result = calculator.calculate_external_score("GMP", advisory_data)
        assert result.is_proxy is True

    def test_external_real_not_proxy(self, calculator):
        """실측 여행경보는 is_proxy=False"""
        advisory_data = [
            {"country_code": "JP", "risk_score": 40, "country_name": "일본"},
        ]
        result = calculator.calculate_external_score("GMP", advisory_data)
        assert result.is_proxy is False

    def test_domestic_airport_not_proxy(self, calculator):
        """국제선 없는 공항은 프록시 경보가 있어도 is_proxy=False (취항국 없음)"""
        advisory_data = [
            {"country_code": "JP", "risk_score": 40, "country_name": "일본", "is_proxy": True},
        ]
        result = calculator.calculate_external_score("KWJ", advisory_data)
        assert result.is_proxy is False
        assert result.has_data is True


class TestHealthScore:
    """보건위험 점수 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RiskCalculator()

    def test_no_quarantine_low_score(self, calculator):
        """검역관리지역 없을 때 낮은 점수"""
        result = calculator.calculate_health_score("ICN", [])
        assert result.score == 5.0

    def test_high_risk_disease_high_score(self, calculator):
        """고위험 질병 발생 시 높은 점수"""
        health_data = [
            {"country_code": "JP", "disease_code": "EBOLA", "risk_score": 95},
        ]
        result = calculator.calculate_health_score("ICN", health_data)
        assert result.score > 50


class TestAviationScore:
    """항공안전 점수 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RiskCalculator()

    def test_no_accidents_low_score(self, calculator):
        """사고 이력 없을 때 낮은 점수"""
        result = calculator.calculate_aviation_score("ICN", [])
        assert result.score == 10.0

    def test_accidents_increase_score(self, calculator):
        """사고 이력이 있으면 점수 증가"""
        aviation_data = [
            {"airport_code": "ICN", "accident_type": "항공기 준사고", "risk_score": 70},
        ]
        result = calculator.calculate_aviation_score("ICN", aviation_data)
        assert result.score > 10


class TestTotalRiskCalculation:
    """종합 위험지수 계산 테스트"""

    @pytest.fixture
    def calculator(self):
        return RiskCalculator()

    def test_total_risk_returns_result(self, calculator):
        """종합 위험지수 계산 결과 반환"""
        result = calculator.calculate_total_risk(
            airport_code="ICN",
            airport_name="인천국제공항"
        )
        assert result is not None
        assert result.airport_code == "ICN"
        assert 0 <= result.total_score <= 100
        assert result.risk_level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]

    def test_total_risk_has_all_categories(self, calculator):
        """모든 카테고리가 포함되어 있는지 확인"""
        result = calculator.calculate_total_risk(
            airport_code="ICN",
            airport_name="인천국제공항"
        )
        expected_categories = ["weather", "external", "health", "operational", "aviation", "security"]
        for cat in expected_categories:
            assert cat in result.categories

    def test_total_risk_with_real_data(self, calculator):
        """실제 데이터로 종합 위험지수 계산"""
        weather_data = {
            "wind_speed": 5.0,
            "precipitation_1h": 0,
            "humidity": 60,
            "precipitation_type": 0,
        }
        result = calculator.calculate_total_risk(
            airport_code="ICN",
            airport_name="인천국제공항",
            weather_data=weather_data,
        )
        assert result.categories["weather"].score < 30  # 좋은 날씨
