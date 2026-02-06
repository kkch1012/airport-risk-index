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
    """카테고리별 위험 점수"""
    code: str
    name: str
    score: float
    level: str
    factors: Dict[str, float]


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
            factors=factors
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

        if not route_countries or not travel_advisory_data:
            # 국제선이 없는 공항이면 외부요인 위험 낮음
            return CategoryScore(
                code="external",
                name="외부요인",
                score=5.0,
                level="LOW",
                factors=factors
            )

        # 취항 국가별 여행경보 점수 계산
        country_scores = []
        high_risk_countries = []

        # 여행경보 데이터를 국가 코드로 인덱싱
        advisory_map = {d["country_code"]: d for d in travel_advisory_data}

        for country_code in route_countries:
            advisory = advisory_map.get(country_code)
            if advisory:
                score = advisory.get("risk_score", 0)
                country_scores.append(score)

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
            factors=factors
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

        if not route_countries or not health_data:
            # 국제선이 없는 공항이면 보건위험 낮음
            return CategoryScore(
                code="health",
                name="보건위험",
                score=5.0,
                level="LOW",
                factors=factors
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
        운영위험 점수 계산 (항공편 지연/결항 데이터 기반)

        Args:
            airport_code: 공항 코드
            operational_data: 운항정보 데이터 리스트

        Returns:
            CategoryScore: 운영위험 점수
        """
        factors = {
            "delay_rate": 0.0,       # 지연율
            "cancellation_rate": 0.0, # 결항율
            "congestion": 0.0,        # 혼잡도
        }

        # 해당 공항 데이터 찾기
        airport_data = None
        for data in operational_data:
            if data.get("airport_code") == airport_code:
                airport_data = data
                break

        if not airport_data:
            # 데이터 없으면 기본 낮은 위험도
            return CategoryScore(
                code="operational",
                name="운영위험",
                score=10.0,
                level="LOW",
                factors=factors
            )

        # 지연율 점수 (0-40점): 지연율 20% 이상이면 최대
        delay_rate = airport_data.get("delay_rate", 0)
        delay_score = min(40, delay_rate * 2)
        factors["delay_rate"] = round(delay_score, 1)

        # 결항율 점수 (0-35점): 결항율 5% 이상이면 최대
        cancel_rate = airport_data.get("cancellation_rate", 0)
        cancel_score = min(35, cancel_rate * 7)
        factors["cancellation_rate"] = round(cancel_score, 1)

        # 혼잡도 점수 (0-25점): 일일 운항편수 기준
        total_flights = airport_data.get("total_flights", 0)
        if total_flights >= 200:
            congestion_score = 25
        elif total_flights >= 100:
            congestion_score = 15
        elif total_flights >= 50:
            congestion_score = 8
        else:
            congestion_score = 3
        factors["congestion"] = round(congestion_score, 1)

        # 최종 점수
        final_score = delay_score + cancel_score + congestion_score
        final_score = min(100, max(0, final_score))

        return CategoryScore(
            code="operational",
            name="운영위험",
            score=round(final_score, 2),
            level=self._get_risk_level(final_score),
            factors=factors
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
            return CategoryScore(
                code="aviation",
                name="항공안전",
                score=10.0,
                level="LOW",
                factors=factors
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

    def calculate_mock_category_score(
        self,
        category_code: str,
        category_name: str,
        seed: str = ""
    ) -> CategoryScore:
        """
        목업 카테고리 점수 생성 (기상 외 카테고리용)

        Args:
            category_code: 카테고리 코드
            category_name: 카테고리 이름
            seed: 랜덤 시드용 문자열

        Returns:
            CategoryScore: 목업 점수
        """
        import random
        random.seed(hash(seed + category_code))

        # 카테고리별 기본 범위 설정
        ranges = {
            "aviation": (10, 50),
            "security": (15, 55),
            "health": (10, 45),
            "operational": (20, 60),
            "external": (10, 40),
        }

        min_val, max_val = ranges.get(category_code, (10, 50))
        score = random.uniform(min_val, max_val)

        # 목업 요인 데이터
        mock_factors = {
            "aviation": {"incident_history": 0, "near_miss": 0, "bird_strike": 0},
            "security": {"terror_threat": 0, "smuggling": 0, "illegal_entry": 0},
            "health": {"disease_alert": 0, "quarantine_cases": 0},
            "operational": {"congestion": 0, "delay_rate": 0},
            "external": {"travel_advisory": 0, "geopolitical": 0},
        }

        factors = mock_factors.get(category_code, {})
        for key in factors:
            factors[key] = round(random.uniform(5, 50), 1)

        return CategoryScore(
            code=category_code,
            name=category_name,
            score=round(score, 2),
            level=self._get_risk_level(score),
            factors=factors
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
    ) -> RiskResult:
        """
        종합 위험지수 계산

        Args:
            airport_code: 공항 코드
            airport_name: 공항 이름
            weather_data: 기상 데이터 (없으면 목업 사용)
            travel_advisory_data: 여행경보 데이터 (없으면 목업 사용)
            health_data: 보건위험 데이터 (없으면 목업 사용)
            operational_data: 운영위험 데이터 (없으면 목업 사용)
            aviation_data: 항공안전 데이터 (없으면 목업 사용)

        Returns:
            RiskResult: 종합 위험지수 결과
        """
        categories = {}
        seed = airport_code + datetime.now().strftime("%Y%m%d")

        # 1. 기상위험 (실제 데이터 또는 목업)
        if weather_data:
            categories["weather"] = self.calculate_weather_score(weather_data)
        else:
            categories["weather"] = self.calculate_mock_category_score(
                "weather", "기상위험", seed
            )

        # 2. 외부요인 (여행경보 + 해외 데이터 또는 목업)
        if travel_advisory_data:
            categories["external"] = self.calculate_external_score(
                airport_code, travel_advisory_data,
                international_weather_data=international_weather_data,
                international_aviation_data=international_aviation_data,
            )
        else:
            categories["external"] = self.calculate_mock_category_score(
                "external", "외부요인", seed
            )

        # 3. 보건위험 (검역관리지역 데이터 또는 목업)
        if health_data:
            categories["health"] = self.calculate_health_score(
                airport_code, health_data
            )
        else:
            categories["health"] = self.calculate_mock_category_score(
                "health", "보건위험", seed
            )

        # 4. 운영위험 (항공편 지연/결항 데이터 또는 목업)
        if operational_data:
            categories["operational"] = self.calculate_operational_score(
                airport_code, operational_data
            )
        else:
            categories["operational"] = self.calculate_mock_category_score(
                "operational", "운영위험", seed
            )

        # 5. 항공안전 (ARAIB 사고 데이터 또는 목업)
        if aviation_data:
            categories["aviation"] = self.calculate_aviation_score(
                airport_code, aviation_data
            )
        else:
            categories["aviation"] = self.calculate_mock_category_score(
                "aviation", "항공안전", seed
            )

        # 6. 보안위협 (현재 목업, 추후 실제 데이터로 대체)
        categories["security"] = self.calculate_mock_category_score(
            "security", "보안위협", seed
        )

        # 3. 종합 점수 계산 (가중 평균)
        total_score = 0
        for code, cat_score in categories.items():
            weight = self.active_weights.get(code, 0.1)
            total_score += cat_score.score * weight

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
