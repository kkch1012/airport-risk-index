"""
위험지수 계산 서비스

각 위험요인을 정규화하고 가중치를 적용하여 종합 위험지수를 산출합니다.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


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

    def __init__(self):
        self.logger = logging.getLogger(__name__)

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
        travel_advisory_data: List[Dict[str, Any]]
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
            "geopolitical": 0.0,  # 추후 국제정세 데이터 연동
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

        # 국제정세 점수는 추후 연동 (현재 여행경보 기반 추정)
        # 여행경보 3단계 이상 국가가 있으면 국제정세 위험 증가
        if any(s >= 70 for s in country_scores):
            factors["geopolitical"] = round(travel_advisory_score * 0.5, 1)

        # 최종 점수: 여행경보 80%, 국제정세 20%
        final_score = factors["travel_advisory"] * 0.8 + factors["geopolitical"] * 0.2
        final_score = min(100, max(0, final_score))

        return CategoryScore(
            code="external",
            name="외부요인",
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
    ) -> RiskResult:
        """
        종합 위험지수 계산

        Args:
            airport_code: 공항 코드
            airport_name: 공항 이름
            weather_data: 기상 데이터 (없으면 목업 사용)
            travel_advisory_data: 여행경보 데이터 (없으면 목업 사용)

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

        # 2. 외부요인 (여행경보 데이터 또는 목업)
        if travel_advisory_data:
            categories["external"] = self.calculate_external_score(
                airport_code, travel_advisory_data
            )
        else:
            categories["external"] = self.calculate_mock_category_score(
                "external", "외부요인", seed
            )

        # 3. 기타 카테고리 (현재 목업, 추후 실제 데이터로 대체)
        category_names = {
            "aviation": "항공안전",
            "security": "보안위협",
            "health": "보건위험",
            "operational": "운영위험",
        }

        for code, name in category_names.items():
            categories[code] = self.calculate_mock_category_score(code, name, seed)

        # 3. 종합 점수 계산 (가중 평균)
        total_score = 0
        for code, cat_score in categories.items():
            weight = self.CATEGORY_WEIGHTS.get(code, 0.1)
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
