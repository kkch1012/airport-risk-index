"""
외교부 여행경보 API 수집기

API: 외교부_국가·지역별 여행경보 목록 조회 (0404 대륙정보)
발급: https://www.data.go.kr/data/15095500/openapi.do

경보단계:
- 1단계: 여행유의 (남색)
- 2단계: 여행자제 (황색)
- 3단계: 출국권고 (적색)
- 4단계: 여행금지 (흑색)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.collectors.base import BaseCollector
from app.config import settings


class TravelAdvisoryCollector(BaseCollector):
    """외교부 여행경보 API 수집기"""

    name = "travel_advisory"
    source_name = "외교부"
    source_url = "http://apis.data.go.kr/1262000/TravelAlarmService0404"
    collection_interval = 21600  # 6시간 (여행경보는 자주 변하지 않음)

    # 경보 단계 매핑
    ALARM_LEVELS = {
        "1": {"level": 1, "name": "여행유의", "color": "blue", "score": 10},
        "2": {"level": 2, "name": "여행자제", "color": "yellow", "score": 40},
        "3": {"level": 3, "name": "출국권고", "color": "red", "score": 70},
        "4": {"level": 4, "name": "여행금지", "color": "black", "score": 100},
    }

    # 한국 공항에서 직항 노선이 있는 주요 국가들 (ISO 2자리 코드)
    # 이 국가들의 여행경보만 수집하여 위험지수에 반영
    TARGET_COUNTRIES = {
        # 동아시아
        "JP": "일본",
        "CN": "중국",
        "TW": "대만",
        "MN": "몽골",
        "HK": "홍콩",
        "MO": "마카오",
        # 동남아시아
        "VN": "베트남",
        "TH": "태국",
        "PH": "필리핀",
        "SG": "싱가포르",
        "MY": "말레이시아",
        "ID": "인도네시아",
        "KH": "캄보디아",
        "LA": "라오스",
        "MM": "미얀마",
        # 중앙/서아시아
        "UZ": "우즈베키스탄",
        "KZ": "카자흐스탄",
        "TR": "튀르키예",
        "AE": "아랍에미리트",
        "QA": "카타르",
        # 남아시아
        "IN": "인도",
        "NP": "네팔",
        "LK": "스리랑카",
        # 오세아니아
        "AU": "호주",
        "NZ": "뉴질랜드",
        "GU": "괌",
        "FJ": "피지",
        "PW": "팔라우",
        # 유럽
        "GB": "영국",
        "FR": "프랑스",
        "DE": "독일",
        "IT": "이탈리아",
        "ES": "스페인",
        "NL": "네덜란드",
        "CH": "스위스",
        "AT": "오스트리아",
        "CZ": "체코",
        "PL": "폴란드",
        "HU": "헝가리",
        "FI": "핀란드",
        "HR": "크로아티아",
        "RU": "러시아",
        # 북미
        "US": "미국",
        "CA": "캐나다",
        # 중남미
        "MX": "멕시코",
        "BR": "브라질",
        # 아프리카
        "EG": "이집트",
        "ET": "에티오피아",
        "KE": "케냐",
        "ZA": "남아프리카공화국",
        "MA": "모로코",
    }

    # 대륙별 분류 (위험도 계산용)
    CONTINENT_MAP = {
        "동북아시아": ["JP", "CN", "TW", "MN", "HK", "MO"],
        "동남아시아": ["VN", "TH", "PH", "SG", "MY", "ID", "KH", "LA", "MM"],
        "중앙아시아": ["UZ", "KZ"],
        "서남아시아": ["TR", "AE", "QA", "IN", "NP", "LK"],
        "오세아니아": ["AU", "NZ", "GU", "FJ", "PW"],
        "유럽": ["GB", "FR", "DE", "IT", "ES", "NL", "CH", "AT", "CZ", "PL", "HU", "FI", "HR", "RU"],
        "북미": ["US", "CA"],
        "중남미": ["MX", "BR"],
        "아프리카": ["EG", "ET", "KE", "ZA", "MA"],
    }

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or settings.DATA_GO_KR_API_KEY

    async def _fetch_travel_alarm_list(self, page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        """
        여행경보 목록 조회

        Args:
            page: 페이지 번호
            per_page: 페이지당 결과 수

        Returns:
            API 응답 데이터
        """
        params = {
            "serviceKey": self.api_key,
            "page": page,
            "perPage": per_page,
            "returnType": "JSON",
        }

        url = f"{self.source_url}/getTravelAlarm0404List?{urlencode(params, safe='=')}"

        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"여행경보 조회 실패: {e}")
            raise

    async def collect(self) -> List[Dict[str, Any]]:
        """모든 국가의 여행경보 데이터 수집"""
        if not self.api_key:
            self.logger.warning("API 키가 설정되지 않았습니다. 목업 데이터를 반환합니다.")
            return self._get_mock_data()

        results = []
        page = 1
        total_count = None

        while True:
            try:
                response = await self._fetch_travel_alarm_list(page=page, per_page=100)

                # 응답 구조 확인
                if "data" in response:
                    items = response.get("data", [])
                    if total_count is None:
                        total_count = response.get("totalCount", len(items))

                    for item in items:
                        country_code = item.get("country_iso_alp2", "")
                        # 대상 국가만 필터링
                        if country_code in self.TARGET_COUNTRIES:
                            results.append({
                                "country_code": country_code,
                                "country_name": item.get("country_nm", ""),
                                "country_name_eng": item.get("country_eng_nm", ""),
                                "alarm_lvl": item.get("alarm_lvl", ""),
                                "continent_code": item.get("continent_cd", ""),
                                "continent_name": item.get("continent_nm", ""),
                                "remark": item.get("remark", ""),
                                "region_ty": item.get("region_ty", ""),
                                "written_dt": item.get("written_dt", ""),
                                "dang_map_download_url": item.get("dang_map_download_url", ""),
                                "flag_download_url": item.get("flag_download_url", ""),
                                "collected_at": datetime.now().isoformat(),
                            })

                    # 다음 페이지 확인
                    if len(items) < 100 or len(results) >= total_count:
                        break
                    page += 1
                else:
                    # 에러 응답 처리
                    error_msg = response.get("resultMsg", "Unknown error")
                    self.logger.error(f"API 오류 응답: {error_msg}")
                    break

            except Exception as e:
                self.logger.error(f"페이지 {page} 수집 실패: {e}")
                break

        self.logger.info(f"여행경보 {len(results)}개국 수집 완료")
        return results

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 응답을 표준 형식으로 변환

        Args:
            raw_data: 수집된 원시 데이터

        Returns:
            변환된 여행경보 데이터
        """
        alarm_lvl = str(raw_data.get("alarm_lvl", "0"))
        alarm_info = self.ALARM_LEVELS.get(alarm_lvl, {"level": 0, "name": "정보없음", "color": "gray", "score": 0})

        # 지역별 경보인 경우 처리 (일부 지역만 경보)
        region_ty = raw_data.get("region_ty", "")
        is_partial = region_ty and region_ty != "전지역"

        return {
            "country_code": raw_data["country_code"],
            "country_name": raw_data["country_name"],
            "country_name_eng": raw_data.get("country_name_eng", ""),
            "continent_name": raw_data.get("continent_name", ""),
            "alarm_level": alarm_info["level"],
            "alarm_name": alarm_info["name"],
            "alarm_color": alarm_info["color"],
            "risk_score": alarm_info["score"],
            "is_partial_warning": is_partial,
            "region_type": region_ty,
            "remark": raw_data.get("remark", ""),
            "written_date": raw_data.get("written_dt", ""),
            "collected_at": raw_data["collected_at"],
            "source": self.source_name,
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        # 국가 코드 필수
        if not data.get("country_code"):
            return False

        # 경보 단계 범위 확인 (0-4)
        alarm_level = data.get("alarm_level", -1)
        if alarm_level < 0 or alarm_level > 4:
            self.logger.warning(f"비정상 경보단계: {alarm_level}")
            return False

        return True

    def _get_mock_data(self) -> List[Dict[str, Any]]:
        """API 키 없을 때 사용할 목업 데이터"""
        import random

        mock_results = []
        now = datetime.now()

        # 시드를 날짜 기반으로 설정하여 같은 날 같은 결과
        random.seed(now.strftime("%Y%m%d"))

        for country_code, country_name in self.TARGET_COUNTRIES.items():
            # 대부분의 국가는 1단계 또는 경보 없음
            # 일부 국가만 높은 경보
            if country_code in ["RU", "MM", "ET"]:
                alarm_lvl = random.choice(["2", "3"])
            elif country_code in ["UA", "SY", "AF"]:
                alarm_lvl = "4"
            else:
                alarm_lvl = random.choices(["", "1", "2"], weights=[0.3, 0.5, 0.2])[0]

            mock_results.append({
                "country_code": country_code,
                "country_name": country_name,
                "country_name_eng": "",
                "alarm_lvl": alarm_lvl,
                "continent_code": "",
                "continent_name": self._get_continent(country_code),
                "remark": f"{country_name} 여행 시 주의사항" if alarm_lvl else "",
                "region_ty": "전지역" if alarm_lvl else "",
                "written_dt": now.strftime("%Y-%m-%d"),
                "collected_at": now.isoformat(),
            })

        return mock_results

    def _get_continent(self, country_code: str) -> str:
        """국가 코드로 대륙명 조회"""
        for continent, countries in self.CONTINENT_MAP.items():
            if country_code in countries:
                return continent
        return "기타"

    def get_summary(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        수집된 데이터의 요약 통계

        Args:
            data_list: 변환된 데이터 리스트

        Returns:
            요약 통계
        """
        level_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        high_risk_countries = []

        for data in data_list:
            level = data.get("alarm_level", 0)
            level_counts[level] = level_counts.get(level, 0) + 1

            if level >= 3:
                high_risk_countries.append({
                    "code": data["country_code"],
                    "name": data["country_name"],
                    "level": level,
                    "alarm_name": data["alarm_name"],
                })

        return {
            "total_countries": len(data_list),
            "level_distribution": {
                "no_warning": level_counts[0],
                "caution": level_counts[1],       # 여행유의
                "restriction": level_counts[2],   # 여행자제
                "advisory": level_counts[3],      # 출국권고
                "prohibition": level_counts[4],   # 여행금지
            },
            "high_risk_countries": high_risk_countries,
            "average_risk_score": sum(d.get("risk_score", 0) for d in data_list) / len(data_list) if data_list else 0,
        }
