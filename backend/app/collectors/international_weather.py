"""
METAR/TAF 해외 공항 기상 데이터 수집기

Source: aviationweather.gov (무료, API 키 불필요)
수집 대상: 한국 직항 노선 주요 해외 공항
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# 주요 해외 공항 ICAO 코드 및 정보
INTERNATIONAL_AIRPORTS = {
    "RJTT": {"iata": "HND", "name": "Tokyo Haneda", "country": "JP"},
    "RJAA": {"iata": "NRT", "name": "Tokyo Narita", "country": "JP"},
    "RJBB": {"iata": "KIX", "name": "Osaka Kansai", "country": "JP"},
    "RJFF": {"iata": "FUK", "name": "Fukuoka", "country": "JP"},
    "ZBAA": {"iata": "PEK", "name": "Beijing Capital", "country": "CN"},
    "ZSPD": {"iata": "PVG", "name": "Shanghai Pudong", "country": "CN"},
    "VHHH": {"iata": "HKG", "name": "Hong Kong", "country": "HK"},
    "RCTP": {"iata": "TPE", "name": "Taipei Taoyuan", "country": "TW"},
    "WSSS": {"iata": "SIN", "name": "Singapore Changi", "country": "SG"},
    "VTBS": {"iata": "BKK", "name": "Bangkok Suvarnabhumi", "country": "TH"},
    "VVNB": {"iata": "HAN", "name": "Hanoi Noi Bai", "country": "VN"},
    "RPLL": {"iata": "MNL", "name": "Manila Ninoy Aquino", "country": "PH"},
    "KLAX": {"iata": "LAX", "name": "Los Angeles", "country": "US"},
    "LFPG": {"iata": "CDG", "name": "Paris CDG", "country": "FR"},
    "EGLL": {"iata": "LHR", "name": "London Heathrow", "country": "GB"},
}

# METAR 기상 위험 기준
WIND_RISK_THRESHOLDS = [(15, 20), (25, 40), (35, 60), (45, 80)]  # (knots, score)
VISIBILITY_RISK_THRESHOLDS = [(5000, 10), (3000, 30), (1500, 50), (800, 70), (400, 90)]


class InternationalWeatherCollector(BaseCollector):
    """해외 공항 METAR 기상 데이터 수집기"""

    name = "international_weather"
    source_name = "Aviation Weather (METAR)"
    source_url = "https://aviationweather.gov/api/data/metar"
    collection_interval = 3600  # 1시간

    async def collect(self) -> List[Dict[str, Any]]:
        """aviationweather.gov에서 METAR 데이터 수집"""
        icao_codes = ",".join(INTERNATIONAL_AIRPORTS.keys())

        try:
            response = await self.client.get(
                self.source_url,
                params={
                    "ids": icao_codes,
                    "format": "json",
                    "hours": 2,
                },
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and data:
                self.logger.info("METAR: %d 건 수집", len(data))
                return data

            self.logger.warning("METAR 응답 비어있음 → 데이터 없음")
            return []

        except Exception as e:
            self.logger.warning("METAR 수집 실패 (%s) → 데이터 없음", e)
            return []

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """METAR JSON → 표준 형식"""
        icao = raw_data.get("icaoId", "")
        airport_info = INTERNATIONAL_AIRPORTS.get(icao, {})

        wind_speed = self._parse_numeric(raw_data.get("wspd", 0), 0)
        wind_gust = self._parse_numeric(raw_data.get("wgst", 0), 0)
        visibility = self._parse_numeric(raw_data.get("visib", 10), 10)
        temp = raw_data.get("temp", None)
        dewpoint = raw_data.get("dewp", None)
        altimeter = raw_data.get("altim", None)
        wx_string = raw_data.get("wxString", "")
        cloud_cover = raw_data.get("cover", "")

        # 위험 점수 계산
        wind_score = self._wind_risk(max(wind_speed, wind_gust))
        vis_score = self._visibility_risk(visibility)
        wx_score = self._weather_phenomena_risk(wx_string)
        total_score = min(100, wind_score * 0.4 + vis_score * 0.3 + wx_score * 0.3)

        return {
            "icao_code": icao,
            "iata_code": airport_info.get("iata", ""),
            "airport_name": airport_info.get("name", icao),
            "country_code": airport_info.get("country", ""),
            "observation_time": raw_data.get("reportTime", ""),
            "wind_speed_kt": wind_speed,
            "wind_gust_kt": wind_gust,
            "visibility_m": self._statute_miles_to_meters(visibility),
            "temperature": temp,
            "dewpoint": dewpoint,
            "altimeter": altimeter,
            "weather_phenomena": wx_string,
            "cloud_cover": cloud_cover,
            "risk_score": round(total_score, 1),
            "risk_factors": {
                "wind": round(wind_score, 1),
                "visibility": round(vis_score, 1),
                "weather": round(wx_score, 1),
            },
            "collected_at": datetime.now().isoformat(),
            "source": self.source_name,
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        return bool(data.get("icao_code")) and data.get("risk_score") is not None

    def _wind_risk(self, speed_kt: float) -> float:
        """풍속 기반 위험 점수"""
        for threshold, score in WIND_RISK_THRESHOLDS:
            if speed_kt < threshold:
                return score
        return 100.0

    def _visibility_risk(self, vis_sm: float) -> float:
        """시정 기반 위험 점수 (statute miles → meters 변환 후 비교)"""
        vis_m = self._statute_miles_to_meters(vis_sm)
        for threshold, score in VISIBILITY_RISK_THRESHOLDS:
            if vis_m > threshold:
                return score
        return 100.0

    def _weather_phenomena_risk(self, wx_string: str) -> float:
        """기상현상 문자열 기반 위험 점수"""
        if not wx_string:
            return 0.0

        wx = wx_string.upper()
        score = 0.0

        # 뇌우
        if "TS" in wx:
            score = max(score, 70.0)
        # 동결
        if "FZ" in wx:
            score = max(score, 60.0)
        # 강한 비/눈
        if "+RA" in wx or "+SN" in wx:
            score = max(score, 50.0)
        # 안개
        if "FG" in wx:
            score = max(score, 40.0)
        # 보통 비/눈
        if "RA" in wx or "SN" in wx:
            score = max(score, 20.0)
        # 박무
        if "BR" in wx or "HZ" in wx:
            score = max(score, 10.0)

        return score

    @staticmethod
    def _parse_numeric(value: Any, default: float = 0) -> float:
        """숫자 또는 '6+', '10+' 같은 문자열을 float로 변환"""
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # "6+", "10+" 등 → 숫자 부분만 추출
            cleaned = value.strip().rstrip("+")
            try:
                return float(cleaned)
            except ValueError:
                return default
        return default

    @staticmethod
    def _statute_miles_to_meters(sm: float) -> float:
        """statute miles → meters"""
        return sm * 1609.34

    def get_country_weather_risk(
        self, data_list: List[Dict[str, Any]], country_code: str
    ) -> float:
        """특정 국가의 공항 평균 기상 위험 점수"""
        country_data = [d for d in data_list if d.get("country_code") == country_code]
        if not country_data:
            return 0.0
        scores = [d.get("risk_score", 0) for d in country_data]
        return round(sum(scores) / len(scores), 1)
