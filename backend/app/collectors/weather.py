"""
기상청 단기예보 API 수집기

API: 기상청_단기예보 ((구)동네예보) 조회서비스
- 초단기실황조회: 현재 기상 실황 데이터
- 단기예보조회: 향후 예보 데이터

발급: https://www.data.go.kr/data/15084084/openapi.do
"""

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.collectors.base import BaseCollector
from app.config import settings


class WeatherCollector(BaseCollector):
    """기상청 단기예보 API 수집기"""

    name = "weather"
    source_name = "기상청"
    source_url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0"
    collection_interval = 3600  # 1시간

    # 공항별 위경도 → 기상청 격자 좌표 (nx, ny)
    # 격자 좌표는 위경도를 기상청 격자로 변환한 값
    AIRPORT_GRIDS = {
        "ICN": {"name": "인천국제공항", "nx": 55, "ny": 124, "lat": 37.4602, "lon": 126.4407},
        "GMP": {"name": "김포국제공항", "nx": 58, "ny": 126, "lat": 37.5583, "lon": 126.7906},
        "PUS": {"name": "김해국제공항", "nx": 98, "ny": 76, "lat": 35.1796, "lon": 128.9382},
        "CJU": {"name": "제주국제공항", "nx": 52, "ny": 38, "lat": 33.5104, "lon": 126.4914},
        "TAE": {"name": "대구국제공항", "nx": 89, "ny": 90, "lat": 35.8941, "lon": 128.6589},
        "CJJ": {"name": "청주국제공항", "nx": 69, "ny": 107, "lat": 36.7166, "lon": 127.4991},
        "KWJ": {"name": "광주공항", "nx": 58, "ny": 74, "lat": 35.1264, "lon": 126.8089},
        "RSU": {"name": "여수공항", "nx": 73, "ny": 66, "lat": 34.8423, "lon": 127.6169},
        "USN": {"name": "울산공항", "nx": 102, "ny": 84, "lat": 35.5935, "lon": 129.3518},
        "KPO": {"name": "포항경주공항", "nx": 102, "ny": 94, "lat": 35.9879, "lon": 129.4204},
        "WJU": {"name": "원주공항", "nx": 76, "ny": 122, "lat": 37.4381, "lon": 127.9601},
        "YNY": {"name": "양양국제공항", "nx": 88, "ny": 138, "lat": 38.0613, "lon": 128.6692},
        "HIN": {"name": "사천공항", "nx": 86, "ny": 69, "lat": 35.0886, "lon": 128.0703},
        "KUV": {"name": "군산공항", "nx": 56, "ny": 92, "lat": 35.9038, "lon": 126.6158},
        "MWX": {"name": "무안국제공항", "nx": 50, "ny": 67, "lat": 34.9914, "lon": 126.3828},
    }

    # 기상 카테고리 코드 매핑
    CATEGORY_MAP = {
        "T1H": "temperature",      # 기온 (℃)
        "RN1": "precipitation_1h", # 1시간 강수량 (mm)
        "UUU": "wind_u",          # 동서바람성분 (m/s)
        "VVV": "wind_v",          # 남북바람성분 (m/s)
        "REH": "humidity",        # 습도 (%)
        "PTY": "precipitation_type",  # 강수형태 (코드)
        "VEC": "wind_direction",  # 풍향 (deg)
        "WSD": "wind_speed",      # 풍속 (m/s)
        # 단기예보 추가 항목
        "POP": "precipitation_prob",  # 강수확률 (%)
        "SKY": "sky_condition",   # 하늘상태 (코드)
        "TMP": "temperature",     # 1시간 기온 (℃)
        "TMN": "temp_min",        # 일 최저기온 (℃)
        "TMX": "temp_max",        # 일 최고기온 (℃)
        "SNO": "snow_depth",      # 1시간 신적설 (cm)
    }

    # 강수형태 코드
    PTY_MAP = {
        "0": "없음",
        "1": "비",
        "2": "비/눈",
        "3": "눈",
        "4": "소나기",
        "5": "빗방울",
        "6": "빗방울눈날림",
        "7": "눈날림",
    }

    # 하늘상태 코드
    SKY_MAP = {
        "1": "맑음",
        "3": "구름많음",
        "4": "흐림",
    }

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or settings.DATA_GO_KR_API_KEY

    def _get_base_datetime(self) -> tuple:
        """
        API 요청용 기준 날짜/시간 계산
        초단기실황: 매시 30분 이후 발표 (정시 기준)
        """
        now = datetime.now()

        # 30분 이전이면 이전 시간 데이터 사용
        if now.minute < 30:
            now = now - timedelta(hours=1)

        base_date = now.strftime("%Y%m%d")
        base_time = now.strftime("%H00")

        return base_date, base_time

    async def _fetch_ultra_srt_ncst(self, nx: int, ny: int) -> Dict[str, Any]:
        """
        초단기실황 조회

        Args:
            nx: 격자 X 좌표
            ny: 격자 Y 좌표

        Returns:
            API 응답 데이터
        """
        base_date, base_time = self._get_base_datetime()

        params = {
            "serviceKey": self.api_key,
            "pageNo": 1,
            "numOfRows": 100,
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": nx,
            "ny": ny,
        }

        url = f"{self.source_url}/getUltraSrtNcst?{urlencode(params, safe='=')}"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"초단기실황 조회 실패 (nx={nx}, ny={ny}): {e}")
            raise

    async def collect(self) -> List[Dict[str, Any]]:
        """모든 공항의 기상 데이터 수집"""
        if not self.api_key:
            self.logger.warning("API 키가 설정되지 않았습니다. 목업 데이터를 반환합니다.")
            return self._get_mock_data()

        results = []

        for airport_code, airport_info in self.AIRPORT_GRIDS.items():
            try:
                response = await self._fetch_ultra_srt_ncst(
                    airport_info["nx"],
                    airport_info["ny"]
                )

                # 응답 파싱
                if response.get("response", {}).get("header", {}).get("resultCode") == "00":
                    items = response["response"]["body"]["items"]["item"]
                    results.append({
                        "airport_code": airport_code,
                        "airport_name": airport_info["name"],
                        "raw_items": items,
                        "collected_at": datetime.now().isoformat(),
                    })
                    self.logger.debug(f"{airport_code} 수집 완료")
                else:
                    error_msg = response.get("response", {}).get("header", {}).get("resultMsg", "Unknown error")
                    self.logger.warning(f"{airport_code} API 오류: {error_msg}")

            except Exception as e:
                self.logger.error(f"{airport_code} 수집 실패: {e}")
                continue

        return results

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 응답을 표준 형식으로 변환

        Args:
            raw_data: 수집된 원시 데이터

        Returns:
            변환된 기상 데이터
        """
        airport_code = raw_data["airport_code"]
        airport_name = raw_data["airport_name"]
        items = raw_data.get("raw_items", [])

        # 카테고리별 데이터 추출
        weather_data = {}
        base_date = None
        base_time = None

        for item in items:
            category = item.get("category")
            value = item.get("obsrValue") or item.get("fcstValue")
            base_date = item.get("baseDate")
            base_time = item.get("baseTime")

            if category in self.CATEGORY_MAP:
                field_name = self.CATEGORY_MAP[category]
                try:
                    # 숫자 변환 시도
                    weather_data[field_name] = float(value) if value not in ["", None] else None
                except (ValueError, TypeError):
                    weather_data[field_name] = value

        # 풍속/풍향이 있으면 강풍 여부 계산
        wind_speed = weather_data.get("wind_speed", 0) or 0
        weather_data["is_strong_wind"] = wind_speed >= 10  # 10m/s 이상

        # 강수형태 텍스트 변환
        pty = weather_data.get("precipitation_type")
        if pty is not None:
            weather_data["precipitation_type_text"] = self.PTY_MAP.get(str(int(pty)), "알 수 없음")

        return {
            "airport_code": airport_code,
            "airport_name": airport_name,
            "base_datetime": f"{base_date}_{base_time}" if base_date else None,
            "collected_at": raw_data["collected_at"],
            "weather": weather_data,
            "source": self.source_name,
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        weather = data.get("weather", {})

        # 필수 필드 확인
        if weather.get("temperature") is None and weather.get("wind_speed") is None:
            return False

        # 온도 범위 검증 (-50 ~ 50)
        temp = weather.get("temperature")
        if temp is not None and (temp < -50 or temp > 50):
            self.logger.warning(f"비정상 온도값: {temp}")
            return False

        # 풍속 범위 검증 (0 ~ 100)
        wind = weather.get("wind_speed")
        if wind is not None and (wind < 0 or wind > 100):
            self.logger.warning(f"비정상 풍속값: {wind}")
            return False

        return True

    def _get_mock_data(self) -> List[Dict[str, Any]]:
        """API 키 없을 때 사용할 목업 데이터"""
        import random

        mock_results = []
        now = datetime.now()

        for airport_code, airport_info in self.AIRPORT_GRIDS.items():
            random.seed(hash(airport_code + now.strftime("%Y%m%d%H")))

            mock_results.append({
                "airport_code": airport_code,
                "airport_name": airport_info["name"],
                "raw_items": [
                    {"category": "T1H", "obsrValue": str(round(random.uniform(-5, 30), 1))},
                    {"category": "RN1", "obsrValue": str(round(random.uniform(0, 10), 1))},
                    {"category": "REH", "obsrValue": str(random.randint(30, 90))},
                    {"category": "WSD", "obsrValue": str(round(random.uniform(0, 15), 1))},
                    {"category": "VEC", "obsrValue": str(random.randint(0, 360))},
                    {"category": "PTY", "obsrValue": str(random.choice([0, 0, 0, 1, 3]))},
                ],
                "collected_at": now.isoformat(),
            })

        return mock_results


# 위경도 → 격자 좌표 변환 함수 (참고용)
def convert_latlon_to_grid(lat: float, lon: float) -> tuple:
    """
    위경도를 기상청 격자 좌표로 변환

    Args:
        lat: 위도
        lon: 경도

    Returns:
        (nx, ny) 격자 좌표
    """
    RE = 6371.00877  # 지구 반경(km)
    GRID = 5.0  # 격자 간격(km)
    SLAT1 = 30.0  # 투영 위도1(degree)
    SLAT2 = 60.0  # 투영 위도2(degree)
    OLON = 126.0  # 기준점 경도(degree)
    OLAT = 38.0  # 기준점 위도(degree)
    XO = 43  # 기준점 X좌표(GRID)
    YO = 136  # 기준점 Y좌표(GRID)

    DEGRAD = math.pi / 180.0

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)

    return nx, ny
