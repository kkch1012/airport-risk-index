"""
보안위협 수집기 + 점수 계산 테스트
"""

import pytest
from datetime import datetime

from app.collectors.security_threat import SecurityThreatCollector
from app.services.risk_calculator import RiskCalculator


class TestSecurityThreatCollector:
    """보안위협 수집기 테스트"""

    @pytest.fixture
    def collector(self):
        return SecurityThreatCollector(api_key="")

    def test_initialization(self, collector):
        """초기화 확인"""
        assert collector.name == "security_threat"
        assert collector.source_name == "보안위협 통합 수집"
        assert collector.collection_interval == 3600

    @pytest.mark.asyncio
    async def test_collect_returns_list(self, collector):
        """수집 결과가 리스트인지 확인 (mock 제거 후 데이터 없으면 빈 리스트)"""
        data = await collector.collect()
        assert isinstance(data, list)

    def test_transform_news_event(self, collector):
        """뉴스 이벤트 변환 테스트"""
        raw = {
            "source_type": "news",
            "threat_type": "terror",
            "title": "인천공항 폭발물 의심 신고",
            "link": "https://example.com/1",
            "collected_at": datetime.now().isoformat(),
        }
        result = collector.transform(raw)
        assert result["source_type"] == "news"
        assert result["threat_type"] == "terror"
        assert result["airport_code"] == "ICN"
        assert 0 <= result["score"] <= 100

    def test_transform_customs_event(self, collector):
        """관세청 데이터 변환 테스트"""
        raw = {
            "source_type": "customs",
            "threat_type": "smuggling",
            "title": "밀수단속 현황",
            "count": 50,
            "collected_at": datetime.now().isoformat(),
        }
        result = collector.transform(raw)
        assert result["source_type"] == "customs"
        assert result["threat_type"] == "smuggling"
        assert 0 <= result["score"] <= 100

    def test_transform_immigration_event(self, collector):
        """출입국 데이터 변환 테스트"""
        raw = {
            "source_type": "immigration",
            "threat_type": "illegal_entry",
            "title": "불법체류 단속",
            "count": 20,
            "collected_at": datetime.now().isoformat(),
        }
        result = collector.transform(raw)
        assert result["source_type"] == "immigration"
        assert result["threat_type"] == "illegal_entry"
        assert 0 <= result["score"] <= 100

    def test_validate_valid_data(self, collector):
        """유효한 데이터 검증"""
        data = {"threat_type": "terror", "score": 50}
        assert collector.validate(data) is True

    def test_validate_missing_threat_type(self, collector):
        """threat_type 없는 데이터 검증 실패"""
        data = {"score": 50}
        assert collector.validate(data) is False

    def test_validate_invalid_score(self, collector):
        """점수 범위 초과 검증 실패"""
        data = {"threat_type": "terror", "score": 150}
        assert collector.validate(data) is False
        data2 = {"threat_type": "terror", "score": -10}
        assert collector.validate(data2) is False

    def test_detect_threat_type(self, collector):
        """위협 유형 탐지"""
        assert collector._detect_threat_type("공항 테러 위협 발생") == "terror"
        assert collector._detect_threat_type("마약 밀수 적발") == "smuggling"
        assert collector._detect_threat_type("불법입국 밀입국 시도") == "illegal_entry"
        assert collector._detect_threat_type("날씨 좋다") == ""

    def test_detect_airport(self, collector):
        """공항 코드 탐지"""
        assert collector._detect_airport("인천공항에서 사건 발생") == "ICN"
        assert collector._detect_airport("김해공항 보안 강화") == "PUS"
        assert collector._detect_airport("관련 없는 뉴스") is None

    def test_calculate_news_threat_score(self, collector):
        """뉴스 위협 점수 계산"""
        # 키워드 없으면 0점
        assert collector._calculate_news_threat_score("오늘 날씨 좋다") == 0
        # 키워드 있으면 점수 양수
        score = collector._calculate_news_threat_score("테러 위협 발생")
        assert score > 0
        # 긴급 키워드 추가 시 더 높은 점수
        score_urgent = collector._calculate_news_threat_score("긴급 속보 테러 폭발물")
        assert score_urgent > score

    def test_calculate_stat_threat_score(self, collector):
        """통계 기반 위협 점수 계산"""
        assert collector._calculate_stat_threat_score("smuggling", 0) == 0
        assert collector._calculate_stat_threat_score("smuggling", 50) == 50.0
        assert collector._calculate_stat_threat_score("smuggling", 200) == 100  # 상한
        assert collector._calculate_stat_threat_score("illegal_entry", 25) == 50.0
        assert collector._calculate_stat_threat_score("illegal_entry", 100) == 100  # 상한
        assert collector._calculate_stat_threat_score("unknown_type", 100) == 0

class TestSecurityScore:
    """calculate_security_score 메서드 테스트"""

    @pytest.fixture
    def calculator(self):
        return RiskCalculator()

    def test_empty_data(self, calculator):
        """빈 데이터 → 낮은 점수"""
        result = calculator.calculate_security_score("ICN", [])
        assert result.code == "security"
        assert result.name == "보안위협"
        assert result.score == 5.0
        assert result.level == "LOW"

    def test_none_data_in_total_risk(self, calculator):
        """security_data=None → mock 사용 (기존 호환)"""
        result = calculator.calculate_total_risk(
            airport_code="ICN",
            airport_name="인천국제공항",
        )
        assert "security" in result.categories
        assert 0 <= result.categories["security"].score <= 100

    def test_terror_only(self, calculator):
        """테러 이벤트만 있는 경우"""
        data = [
            {"threat_type": "terror", "score": 80, "airport_code": "ICN"},
        ]
        result = calculator.calculate_security_score("ICN", data)
        assert result.factors["terror_threat"] > 0
        assert result.factors["smuggling"] == 0
        assert result.factors["illegal_entry"] == 0
        assert result.score > 0

    def test_smuggling_only(self, calculator):
        """밀수 이벤트만 있는 경우"""
        data = [
            {"threat_type": "smuggling", "score": 60, "airport_code": None},
        ]
        result = calculator.calculate_security_score("ICN", data)
        assert result.factors["terror_threat"] == 0
        assert result.factors["smuggling"] > 0
        assert result.factors["illegal_entry"] == 0

    def test_illegal_entry_only(self, calculator):
        """불법입국 이벤트만 있는 경우"""
        data = [
            {"threat_type": "illegal_entry", "score": 50, "airport_code": "ICN"},
        ]
        result = calculator.calculate_security_score("ICN", data)
        assert result.factors["terror_threat"] == 0
        assert result.factors["smuggling"] == 0
        assert result.factors["illegal_entry"] > 0

    def test_mixed_events(self, calculator):
        """혼합 이벤트"""
        data = [
            {"threat_type": "terror", "score": 70, "airport_code": "ICN"},
            {"threat_type": "smuggling", "score": 50, "airport_code": None},
            {"threat_type": "illegal_entry", "score": 40, "airport_code": "ICN"},
        ]
        result = calculator.calculate_security_score("ICN", data)
        assert result.factors["terror_threat"] > 0
        assert result.factors["smuggling"] > 0
        assert result.factors["illegal_entry"] > 0
        assert 0 < result.score <= 100

    def test_score_range(self, calculator):
        """점수가 항상 0-100 범위"""
        # 매우 높은 점수 입력
        data = [
            {"threat_type": "terror", "score": 100, "airport_code": "ICN"},
            {"threat_type": "terror", "score": 100, "airport_code": "ICN"},
            {"threat_type": "smuggling", "score": 100, "airport_code": "ICN"},
            {"threat_type": "smuggling", "score": 100, "airport_code": "ICN"},
            {"threat_type": "illegal_entry", "score": 100, "airport_code": "ICN"},
            {"threat_type": "illegal_entry", "score": 100, "airport_code": "ICN"},
        ]
        result = calculator.calculate_security_score("ICN", data)
        assert 0 <= result.score <= 100
        assert 0 <= result.factors["terror_threat"] <= 40
        assert 0 <= result.factors["smuggling"] <= 30
        assert 0 <= result.factors["illegal_entry"] <= 30

    def test_airport_filtering(self, calculator):
        """공항별 + 전체(None) 데이터 모두 포함"""
        data = [
            {"threat_type": "terror", "score": 60, "airport_code": "ICN"},
            {"threat_type": "smuggling", "score": 40, "airport_code": None},
            {"threat_type": "terror", "score": 80, "airport_code": "PUS"},  # 다른 공항 → 제외
        ]
        result_icn = calculator.calculate_security_score("ICN", data)
        result_pus = calculator.calculate_security_score("PUS", data)
        # ICN은 자기 공항 + None(전체), PUS는 자기 공항 + None(전체)
        assert result_icn.factors["terror_threat"] > 0
        assert result_icn.factors["smuggling"] > 0
        assert result_pus.factors["terror_threat"] > 0
        assert result_pus.factors["smuggling"] > 0

    def test_risk_level_assignment(self, calculator):
        """위험등급 할당 확인"""
        # 빈 데이터 → LOW
        result = calculator.calculate_security_score("ICN", [])
        assert result.level == "LOW"

    def test_total_risk_with_security_data(self, calculator):
        """calculate_total_risk에 security_data 전달"""
        security_data = [
            {"threat_type": "terror", "score": 60, "airport_code": "ICN"},
            {"threat_type": "smuggling", "score": 40, "airport_code": None},
        ]
        result = calculator.calculate_total_risk(
            airport_code="ICN",
            airport_name="인천국제공항",
            security_data=security_data,
        )
        assert "security" in result.categories
        sec = result.categories["security"]
        assert sec.factors["terror_threat"] > 0
        assert sec.factors["smuggling"] > 0

    def test_zero_score_events(self, calculator):
        """점수 0인 이벤트"""
        data = [
            {"threat_type": "terror", "score": 0, "airport_code": "ICN"},
        ]
        result = calculator.calculate_security_score("ICN", data)
        assert result.factors["terror_threat"] == 0
        assert result.score <= 5.0  # 매우 낮은 점수
