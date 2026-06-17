"""
위험지수 계산 서비스

각 위험요인을 정규화하고 가중치를 적용하여 종합 위험지수를 산출합니다.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# 질병별 위험도 점수 (보건위험 계산용)
DISEASE_RISK_SCORES = {
    "EBOLA": 95,
    "MARBURG": 95,
    "PLAGUE": 90,
    "LASSAFEVER": 90,
    "MERS": 85,
    "NIPAH": 85,
    "YELLOWFEVER": 80,
    "POLIOVIRUS": 80,
    "AVIANFLU": 75,
    "CHOLERA": 70,
    "MPOX": 60,
    "ZIKA": 60,
    "DENGUE": 55,
    "CHIKUNGUNYA": 55,
    "COVID19": 50,
    "MALARIA": 50,
    "UNKNOWN": 40,
}


# 공항별 국제 노선 취항 국가 (여행경보 연동용)
# 실제로는 더 많은 노선이 있지만, 주요 노선만 포함
AIRPORT_INTERNATIONAL_ROUTES = {
    "ICN": ["JP", "CN", "US", "TH", "VN", "TW", "PH", "SG", "HK", "DE", "FR", "GB", "AU", "ID", "MY"],  # 인천: 대부분의 국제선
    "GMP": ["JP", "CN", "TW"],  # 김포: 일본, 중국, 대만
    "PUS": ["JP", "CN", "TW", "VN", "TH", "PH"],  # 김해: 동아시아, 동남아
    "CJU": ["JP", "CN", "TW", "HK", "MO"],  # 제주: 일본, 중국, 대만, 홍콩, 마카오
    "TAE": ["JP", "CN", "TW", "VN", "TH"],  # 대구: 일본, 중국 등
    "CJJ": ["JP", "CN", "TW", "VN", "TH", "PH"],  # 청주: 일본, 중국, 동남아
    "MWX": ["JP", "CN", "TW", "VN", "TH"],  # 무안: 일본, 중국, 동남아
    "YNY": ["JP", "CN", "TW"],  # 양양: 일본, 중국, 대만
    # 나머지 국내선 전용 공항은 국제선 없음
    "KWJ": [], "RSU": [], "USN": [], "KPO": [], "WJU": [], "HIN": [], "KUV": [],
}


@dataclass
class CategoryScore:
    """카테고리별 위험 점수

    has_data=False 인 경우 해당 카테고리의 데이터 소스(수집기)에서
    유효한 데이터를 얻지 못해 점수가 중립(neutral) 기본값임을 의미한다.
    이 카테고리는 종합 위험지수 계산 시 가중치에서 제외(재정규화)된다.

    is_proxy=True 인 경우 점수가 실측 통계가 아니라 뉴스 신호량 기반
    추정 프록시(예: 운항 지연율, 여행경보 단계)로 산출되었음을 의미한다.
    (프론트/리포트에서 "추정치"로 구분 표기)
    """
    code: str
    name: str
    score: float
    level: str
    factors: Dict[str, float]
    has_data: bool = True
    is_proxy: bool = False


@dataclass
class RiskResult:
    """위험지수 계산 결과"""
    airport_code: str
    airport_name: str
    date: str
    total_score: float
    risk_level: str
    categories: Dict[str, CategoryScore]
    updated_at: str


class RiskCalculator:
    """위험지수 계산기"""

    # 위험등급 기준
    RISK_LEVELS = [
        (0, 25, "LOW"),
        (25, 50, "MODERATE"),
        (50, 75, "HIGH"),
        (75, 100, "CRITICAL"),
    ]

    # 카테고리별 가중치
    CATEGORY_WEIGHTS = {
        "weather": 0.20,      # 기상위험
        "aviation": 0.25,     # 항공안전
        "security": 0.20,     # 보안위협
        "health": 0.15,       # 보건위험
        "operational": 0.10,  # 운영위험
        "external": 0.10,     # 외부요인
    }

    # 기상 요인별 정규화 설정
    WEATHER_NORMALIZATION = {
        "wind_speed": {
            "min": 0,
            "max": 20,      # 20m/s 이상이면 최대 위험
            "weight": 0.35,
        },
        "precipitation_1h": {
            "min": 0,
            "max": 30,      # 30mm/h 이상이면 최대 위험
            "weight": 0.25,
        },
        "humidity": {
            "min": 30,
            "max": 95,      # 습도는 참고용 (가중치 낮음)
            "weight": 0.10,
        },
        "precipitation_type": {
            # 강수형태: 0=없음, 1=비, 2=비/눈, 3=눈, 4=소나기
            "scores": {0: 0, 1: 50, 2: 70, 3: 80, 4: 40, 5: 20, 6: 30, 7: 30},
            "weight": 0.30,
        },
    }

    def __init__(self, custom_weights: Optional[Dict[str, float]] = None):
        self.logger = logging.getLogger(__name__)
        self._custom_weights = custom_weights

    @property
    def active_weights(self) -> Dict[str, float]:
        """동적 가중치 반환. custom_weights가 없으면 기본값 사용."""
        return self._custom_weights or self.CATEGORY_WEIGHTS

    def calculate_weather_score(self, weather_data: Dict[str, Any]) -> CategoryScore:
        """
        기상 데이터로부터 기상위험 점수 계산

        Args:
            weather_data: 기상 수집기에서 가져온 데이터

        Returns:
            CategoryScore: 기상위험 점수
        """
        factors = {}
        weighted_sum = 0
        total_weight = 0

        # 풍속 정규화
        wind_speed = weather_data.get("wind_speed")
        if wind_speed is not None:
            config = self.WEATHER_NORMALIZATION["wind_speed"]
            normalized = self._normalize_value(
                wind_speed, config["min"], config["max"]
            )
            factors["wind_speed"] = round(normalized, 1)
            weighted_sum += normalized * config["weight"]
            total_weight += config["weight"]

        # 강수량 정규화
        precipitation = weather_data.get("precipitation_1h", 0) or 0
        config = self.WEATHER_NORMALIZATION["precipitation_1h"]
        normalized = self._normalize_value(
            precipitation, config["min"], config["max"]
        )
        factors["precipitation"] = round(normalized, 1)
        weighted_sum += normalized * config["weight"]
        total_weight += config["weight"]

        # 습도 정규화 (높을수록 약간 위험)
        humidity = weather_data.get("humidity")
        if humidity is not None:
            config = self.WEATHER_NORMALIZATION["humidity"]
            # 습도는 70% 이상일 때 위험도 증가
            if humidity > 70:
                normalized = self._normalize_value(humidity, 70, config["max"])
            else:
                normalized = 0
            factors["humidity"] = round(normalized, 1)
            weighted_sum += normalized * config["weight"]
            total_weight += config["weight"]

        # 강수형태
        pty = weather_data.get("precipitation_type", 0)
        config = self.WEATHER_NORMALIZATION["precipitation_type"]
        pty_score = config["scores"].get(int(pty) if pty else 0, 0)
        factors["precipitation_type"] = pty_score
        weighted_sum += pty_score * config["weight"]
        total_weight += config["weight"]

        # 최종 점수 계산
        score = weighted_sum / total_weight if total_weight > 0 else 0
        score = min(100, max(0, score))

        return CategoryScore(
            code="weather",
            name="기상위험",
            score=round(score, 2),
            level=self._get_risk_level(score),
            factors=factors,
            has_data=bool(factors),
        )

    def calculate_external_score(
        self,
        airport_code: str,
        travel_advisory_data: List[Dict[str, Any]],
        international_weather_data: Optional[List[Dict[str, Any]]] = None,
        international_aviation_data: Optional[List[Dict[str, Any]]] = None,
    ) -> CategoryScore:
        """
        외부요인 위험 점수 계산 (여행경보 기반)

        Args:
            airport_code: 공항 코드
            travel_advisory_data: 여행경보 데이터 리스트

        Returns:
            CategoryScore: 외부요인 위험 점수
        """
        factors = {
            "travel_advisory": 0.0,
            "geopolitical": 0.0,
            "intl_weather": 0.0,
            "intl_aviation": 0.0,
        }

        # 해당 공항의 국제 노선 취항 국가 조회
        route_countries = AIRPORT_INTERNATIONAL_ROUTES.get(airport_code, [])

        if not route_countries:
            # 국제선이 없는 공항이면 외부요인 위험 낮음 (실제 판정 → has_data=True)
            return CategoryScore(
                code="external",
                name="외부요인",
                score=5.0,
                level="LOW",
                factors=factors,
                has_data=True,
            )

        if not travel_advisory_data:
            # 여행경보 데이터 소스가 비어있음 → 중립 + 데이터 없음
            return CategoryScore(
                code="external",
                name="외부요인",
                score=5.0,
                level="LOW",
                factors=factors,
                has_data=False,
            )

        # 취항 국가별 여행경보 점수 계산
        country_scores = []
        high_risk_countries = []
        used_proxy = False  # 매칭된 여행경보가 뉴스 프록시였는지

        # 여행경보 데이터를 국가 코드로 인덱싱
        advisory_map = {d["country_code"]: d for d in travel_advisory_data}

        for country_code in route_countries:
            advisory = advisory_map.get(country_code)
            if advisory:
                score = advisory.get("risk_score", 0)
                country_scores.append(score)
                if advisory.get("is_proxy"):
                    used_proxy = True

                if score >= 40:  # 여행자제 이상
                    high_risk_countries.append({
                        "code": country_code,
                        "name": advisory.get("country_name", country_code),
                        "level": advisory.get("alarm_name", ""),
                        "score": score,
                    })
            else:
                country_scores.append(0)  # 경보 없음

        # 여행경보 점수: 가중 평균 (고위험 국가에 가중치)
        if country_scores:
            # 최대값과 평균의 조합
            max_score = max(country_scores)
            avg_score = sum(country_scores) / len(country_scores)
            # 최대값 70%, 평균 30% 반영
            travel_advisory_score = max_score * 0.7 + avg_score * 0.3
        else:
            travel_advisory_score = 0

        factors["travel_advisory"] = round(travel_advisory_score, 1)

        # 국제정세 점수 (여행경보 3단계 이상 기반)
        if any(s >= 70 for s in country_scores):
            factors["geopolitical"] = round(travel_advisory_score * 0.5, 1)

        # 해외 기상 위험 (취항 국가 공항의 평균 기상 위험)
        if international_weather_data and route_countries:
            intl_weather_scores = [
                w.get("risk_score", 0)
                for w in international_weather_data
                if w.get("country_code") in route_countries
            ]
            if intl_weather_scores:
                factors["intl_weather"] = round(
                    max(intl_weather_scores) * 0.6 + sum(intl_weather_scores) / len(intl_weather_scores) * 0.4,
                    1,
                )

        # 해외 항공사고 위험 (취항 국가의 최근 사고)
        if international_aviation_data and route_countries:
            intl_aviation_scores = [
                a.get("risk_score", 0)
                for a in international_aviation_data
                if a.get("country_code") in route_countries
            ]
            if intl_aviation_scores:
                factors["intl_aviation"] = round(
                    max(intl_aviation_scores) * 0.7 + sum(intl_aviation_scores) / len(intl_aviation_scores) * 0.3,
                    1,
                )

        # 최종 점수: 여행경보 50%, 국제정세 15%, 해외기상 20%, 해외항공 15%
        final_score = (
            factors["travel_advisory"] * 0.50
            + factors["geopolitical"] * 0.15
            + factors["intl_weather"] * 0.20
            + factors["intl_aviation"] * 0.15
        )
        final_score = min(100, max(0, final_score))

        return CategoryScore(
            code="external",
            name="외부요인",
            score=round(final_score, 2),
            level=self._get_risk_level(final_score),
            factors=factors,
            # 여행경보가 뉴스 프록시 기반이면 추정치로 표시
            is_proxy=used_proxy,
        )

    def calculate_health_score(
        self,
        airport_code: str,
        health_data: List[Dict[str, Any]]
    ) -> CategoryScore:
        """
        보건위험 점수 계산 (검역관리지역 데이터 기반)

        Args:
            airport_code: 공항 코드
            health_data: 검역관리지역 데이터 리스트

        Returns:
            CategoryScore: 보건위험 점수
        """
        factors = {
            "disease_alert": 0.0,      # 감염병 경보 수준
            "quarantine_cases": 0.0,    # 검역관리지역 수
            "outbreak_proximity": 0.0,  # 발생지 근접도
        }

        # 해당 공항의 국제 노선 취항 국가
        route_countries = AIRPORT_INTERNATIONAL_ROUTES.get(airport_code, [])

        if not route_countries:
            # 국제선이 없는 공항이면 보건위험 낮음 (실제 판정 → has_data=True)
            return CategoryScore(
                code="health",
                name="보건위험",
                score=5.0,
                level="LOW",
                factors=factors,
                has_data=True,
            )

        if not health_data:
            # 검역/감염병 데이터 소스가 비어있음 → 중립 + 데이터 없음
            return CategoryScore(
                code="health",
                name="보건위험",
                score=5.0,
                level="LOW",
                factors=factors,
                has_data=False,
            )

        # 국가별 위험도 맵 구축 (여러 질병이 있을 수 있으므로 최대값 사용)
        country_risk_map = {}
        country_disease_count = {}

        for item in health_data:
            country_code = item.get("country_code", "")
            if not country_code:
                continue

            disease_code = item.get("disease_code", "UNKNOWN")
            risk_score = item.get("risk_score", 0)

            # 질병 코드 기반 위험도가 없으면 기본값 사용
            if risk_score == 0:
                risk_score = DISEASE_RISK_SCORES.get(disease_code, 40)

            # 국가별 최대 위험도
            if country_code not in country_risk_map:
                country_risk_map[country_code] = 0
                country_disease_count[country_code] = 0

            country_risk_map[country_code] = max(
                country_risk_map[country_code],
                risk_score
            )
            country_disease_count[country_code] += 1

        # 취항 국가 중 검역관리지역 필터링
        affected_scores = []
        affected_count = 0

        for country_code in route_countries:
            if country_code in country_risk_map:
                affected_scores.append(country_risk_map[country_code])
                affected_count += country_disease_count.get(country_code, 0)

        # 점수 계산
        if affected_scores:
            # 감염병 경보 수준: 최대값 70% + 평균 30%
            max_score = max(affected_scores)
            avg_score = sum(affected_scores) / len(affected_scores)
            factors["disease_alert"] = round(max_score * 0.7 + avg_score * 0.3, 1)

            # 검역관리지역 수 (10개 이상이면 최대)
            quarantine_factor = min(100, affected_count * 10)
            factors["quarantine_cases"] = round(quarantine_factor, 1)

            # 발생지 근접도: 취항 국가 중 감염지역 비율
            proximity_factor = (len(affected_scores) / len(route_countries)) * 100
            factors["outbreak_proximity"] = round(proximity_factor, 1)
        else:
            factors["disease_alert"] = 0
            factors["quarantine_cases"] = 0
            factors["outbreak_proximity"] = 0

        # 최종 점수: 감염병 경보 60%, 검역관리지역 수 20%, 근접도 20%
        final_score = (
            factors["disease_alert"] * 0.6 +
            factors["quarantine_cases"] * 0.2 +
            factors["outbreak_proximity"] * 0.2
        )
        final_score = min(100, max(0, final_score))

        return CategoryScore(
            code="health",
            name="보건위험",
            score=round(final_score, 2),
            level=self._get_risk_level(final_score),
            factors=factors
        )

    def calculate_operational_score(
        self,
        airport_code: str,
        operational_data: List[Dict[str, Any]]
    ) -> CategoryScore:
        """
        운영위험 점수 계산 (항공편 지연 중심)

        크롤링/공개데이터만으로 산출 가능한 지표(지연율·결항율)에 집중한다.
        혼잡도(시간대별 운항편수)·시설노후도·파업 등 운영자 내부 데이터가
        필요한 지표는 제외하고, 지연율을 주축(0-65)으로 결항율(0-35)을 보조로 둔다.

        Args:
            airport_code: 공항 코드
            operational_data: 운항정보 데이터 리스트

        Returns:
            CategoryScore: 운영위험 점수
        """
        factors = {
            "delay_rate": 0.0,        # 지연율 (주축)
            "cancellation_rate": 0.0,  # 결항율 (보조)
        }

        # 해당 공항 데이터 찾기
        airport_data = None
        for data in operational_data:
            if data.get("airport_code") == airport_code:
                airport_data = data
                break

        if not airport_data:
            # 운항 데이터 소스 없음 → 중립 + 데이터 없음
            return CategoryScore(
                code="operational",
                name="운영위험",
                score=10.0,
                level="LOW",
                factors=factors,
                has_data=False,
            )

        # 지연율 점수 (0-65점): 지연율 26% 이상이면 최대
        delay_rate = airport_data.get("delay_rate", 0)
        delay_score = min(65, delay_rate * 2.5)
        factors["delay_rate"] = round(delay_score, 1)

        # 결항율 점수 (0-35점): 결항율 7% 이상이면 최대
        cancel_rate = airport_data.get("cancellation_rate", 0)
        cancel_score = min(35, cancel_rate * 5)
        factors["cancellation_rate"] = round(cancel_score, 1)

        # 최종 점수 (지연 중심)
        final_score = delay_score + cancel_score
        final_score = min(100, max(0, final_score))

        return CategoryScore(
            code="operational",
            name="운영위험",
            score=round(final_score, 2),
            level=self._get_risk_level(final_score),
            factors=factors,
            has_data=True,
            # 뉴스 신호 기반 폴백(실측 운항통계 아님)이면 추정치로 표시
            is_proxy=bool(airport_data.get("is_proxy")),
        )

    def calculate_aviation_score(
        self,
        airport_code: str,
        aviation_data: List[Dict[str, Any]]
    ) -> CategoryScore:
        """
        항공안전 점수 계산 (ARAIB 사고 데이터 기반)

        Args:
            airport_code: 공항 코드
            aviation_data: 항공사고 데이터 리스트

        Returns:
            CategoryScore: 항공안전 점수
        """
        factors = {
            "incident_history": 0.0,  # 사고 이력 점수
            "near_miss": 0.0,         # 준사고 점수
            "severity": 0.0,          # 사고 심각도
        }

        # 해당 공항 사고 필터링
        airport_accidents = [
            d for d in aviation_data
            if d.get("airport_code") == airport_code
        ]

        # 전체 사고 중 항공기 사고/준사고만 필터 (공항 관계없이)
        all_aircraft_accidents = [
            d for d in aviation_data
            if "항공기" in d.get("accident_type", "")
        ]

        if not airport_accidents and not all_aircraft_accidents:
            # 사고 데이터 없음 = 낮은 위험
            # 입력 자체가 비어있으면 데이터 소스 부재(has_data=False),
            # 데이터는 있으나 항공기 사고가 없으면 실제 낮은 위험(has_data=True)
            return CategoryScore(
                code="aviation",
                name="항공안전",
                score=10.0,
                level="LOW",
                factors=factors,
                has_data=bool(aviation_data),
            )

        # 1. 해당 공항 사고 이력 점수 (0-40점)
        airport_count = len(airport_accidents)
        factors["incident_history"] = min(40, airport_count * 12)

        # 2. 준사고 점수 (0-30점) - 전체 항공기 준사고 기반
        near_miss_count = sum(
            1 for d in all_aircraft_accidents
            if "준사고" in d.get("accident_type", "")
        )
        factors["near_miss"] = min(30, near_miss_count * 6)

        # 3. 심각도 점수 (0-30점) - 최근 사고 심각도
        if airport_accidents:
            severity_scores = [d.get("risk_score", 30) for d in airport_accidents]
            avg_severity = sum(severity_scores) / len(severity_scores)
            factors["severity"] = round(avg_severity * 0.3, 1)
        else:
            # 공항 직접 사고 없으면 전체 평균의 일부 반영
            if all_aircraft_accidents:
                all_scores = [d.get("risk_score", 30) for d in all_aircraft_accidents]
                avg_all = sum(all_scores) / len(all_scores)
                factors["severity"] = round(avg_all * 0.15, 1)

        # 최종 점수
        final_score = (
            factors["incident_history"] +
            factors["near_miss"] +
            factors["severity"]
        )
        final_score = min(100, max(0, final_score))

        return CategoryScore(
            code="aviation",
            name="항공안전",
            score=round(final_score, 2),
            level=self._get_risk_level(final_score),
            factors=factors
        )

    def calculate_security_score(
        self,
        airport_code: str,
        security_data: List[Dict[str, Any]]
    ) -> CategoryScore:
        """
        보안위협 점수 계산 (뉴스 키워드 + 밀수 + 불법입국 데이터 기반)

        Args:
            airport_code: 공항 코드
            security_data: 보안위협 수집 데이터 리스트

        Returns:
            CategoryScore: 보안위협 점수
        """
        factors = {
            "terror_threat": 0.0,   # 테러/위협 (0-40)
            "smuggling": 0.0,       # 밀수 (0-30)
            "illegal_entry": 0.0,   # 불법입국 (0-30)
        }

        if not security_data:
            return CategoryScore(
                code="security",
                name="보안위협",
                score=5.0,
                level="LOW",
                factors=factors,
                has_data=False,
            )

        # 공항별 + 전체(공항 미지정) 데이터 분리
        airport_events = [
            d for d in security_data
            if d.get("airport_code") == airport_code or d.get("airport_code") is None
        ]

        # 유형별 점수 집계
        terror_scores = []
        smuggling_scores = []
        illegal_scores = []

        for event in airport_events:
            threat_type = event.get("threat_type", "")
            score = event.get("score", 0)

            if threat_type == "terror":
                terror_scores.append(score)
            elif threat_type == "smuggling":
                smuggling_scores.append(score)
            elif threat_type == "illegal_entry":
                illegal_scores.append(score)

        # terror_threat: 최대값 60% + 평균 40%, 상한 40점
        if terror_scores:
            max_t = max(terror_scores)
            avg_t = sum(terror_scores) / len(terror_scores)
            factors["terror_threat"] = round(min(40, (max_t * 0.6 + avg_t * 0.4) * 0.4), 1)

        # smuggling: 최대값 60% + 평균 40%, 상한 30점
        if smuggling_scores:
            max_s = max(smuggling_scores)
            avg_s = sum(smuggling_scores) / len(smuggling_scores)
            factors["smuggling"] = round(min(30, (max_s * 0.6 + avg_s * 0.4) * 0.3), 1)

        # illegal_entry: 최대값 60% + 평균 40%, 상한 30점
        if illegal_scores:
            max_i = max(illegal_scores)
            avg_i = sum(illegal_scores) / len(illegal_scores)
            factors["illegal_entry"] = round(min(30, (max_i * 0.6 + avg_i * 0.4) * 0.3), 1)

        # 최종 점수: 3개 요인 합산
        final_score = (
            factors["terror_threat"]
            + factors["smuggling"]
            + factors["illegal_entry"]
        )
        final_score = min(100, max(0, final_score))

        return CategoryScore(
            code="security",
            name="보안위협",
            score=round(final_score, 2),
            level=self._get_risk_level(final_score),
            factors=factors
        )

    def _no_data_category(self, code: str, name: str) -> CategoryScore:
        """
        데이터 소스가 비어있을 때의 중립 카테고리 점수.

        랜덤 목업을 생성하지 않는다. 점수는 중립 기본값(낮음)이며
        has_data=False 로 표시되어 종합 위험지수 가중치에서 제외된다.
        """
        return CategoryScore(
            code=code,
            name=name,
            score=0.0,
            level="LOW",
            factors={},
            has_data=False,
        )

    def calculate_total_risk(
        self,
        airport_code: str,
        airport_name: str,
        weather_data: Optional[Dict[str, Any]] = None,
        travel_advisory_data: Optional[List[Dict[str, Any]]] = None,
        health_data: Optional[List[Dict[str, Any]]] = None,
        operational_data: Optional[List[Dict[str, Any]]] = None,
        aviation_data: Optional[List[Dict[str, Any]]] = None,
        international_weather_data: Optional[List[Dict[str, Any]]] = None,
        international_aviation_data: Optional[List[Dict[str, Any]]] = None,
        security_data: Optional[List[Dict[str, Any]]] = None,
    ) -> RiskResult:
        """
        종합 위험지수 계산

        데이터가 없는 카테고리는 has_data=False로 표시되어 종합점수 가중치에서
        제외(재정규화)된다. 랜덤 목업은 생성하지 않는다.

        Args:
            airport_code: 공항 코드
            airport_name: 공항 이름
            weather_data: 기상 데이터 (없으면 has_data=False)
            travel_advisory_data: 여행경보 데이터 (없으면 has_data=False)
            health_data: 보건위험 데이터 (없으면 has_data=False)
            operational_data: 운영위험 데이터 (없으면 has_data=False)
            aviation_data: 항공안전 데이터 (없으면 has_data=False)

        Returns:
            RiskResult: 종합 위험지수 결과
        """
        categories = {}

        # 1. 기상위험 (실제 데이터 없으면 '데이터 없음')
        if weather_data:
            categories["weather"] = self.calculate_weather_score(weather_data)
        else:
            categories["weather"] = self._no_data_category("weather", "기상위험")

        # 2. 외부요인 (여행경보 + 해외 데이터)
        #    국제선 없는 공항은 데이터 없이도 실제 LOW 판정이 가능하므로 항상 호출
        categories["external"] = self.calculate_external_score(
            airport_code, travel_advisory_data or [],
            international_weather_data=international_weather_data,
            international_aviation_data=international_aviation_data,
        )

        # 3. 보건위험 (검역관리지역/감염병 데이터)
        categories["health"] = self.calculate_health_score(
            airport_code, health_data or []
        )

        # 4. 운영위험 (항공편 지연/결항 데이터)
        categories["operational"] = self.calculate_operational_score(
            airport_code, operational_data or []
        )

        # 5. 항공안전 (ARAIB 사고 데이터)
        categories["aviation"] = self.calculate_aviation_score(
            airport_code, aviation_data or []
        )

        # 6. 보안위협
        categories["security"] = self.calculate_security_score(
            airport_code, security_data or []
        )

        # 종합 점수 계산 (실데이터 카테고리만 가중치 재정규화)
        #   has_data=False 카테고리는 가짜 점수가 아니므로 제외하고,
        #   남은 카테고리 가중치를 합이 1이 되도록 재정규화한다.
        available = {
            code: cat for code, cat in categories.items() if cat.has_data
        }
        weight_sum = sum(self.active_weights.get(code, 0.1) for code in available)
        if weight_sum > 0:
            total_score = sum(
                cat.score * self.active_weights.get(code, 0.1)
                for code, cat in available.items()
            ) / weight_sum
        else:
            # 가용 데이터가 전혀 없으면 위험지수 산출 불가 → 0
            total_score = 0.0
        total_score = round(min(100, max(0, total_score)), 2)

        return RiskResult(
            airport_code=airport_code,
            airport_name=airport_name,
            date=datetime.now().strftime("%Y-%m-%d"),
            total_score=round(total_score, 2),
            risk_level=self._get_risk_level(total_score),
            categories=categories,
            updated_at=datetime.now().isoformat()
        )

    def _normalize_value(
        self,
        value: float,
        min_val: float,
        max_val: float,
        inverse: bool = False
    ) -> float:
        """
        값을 0-100 범위로 정규화

        Args:
            value: 원본 값
            min_val: 최소값 (0점)
            max_val: 최대값 (100점)
            inverse: True면 값이 낮을수록 위험

        Returns:
            정규화된 값 (0-100)
        """
        if max_val == min_val:
            return 0

        normalized = (value - min_val) / (max_val - min_val) * 100
        normalized = max(0, min(100, normalized))

        if inverse:
            normalized = 100 - normalized

        return normalized

    def _get_risk_level(self, score: float) -> str:
        """점수에 따른 위험등급 반환"""
        for min_val, max_val, level in self.RISK_LEVELS:
            if min_val <= score < max_val:
                return level
        return "CRITICAL"
