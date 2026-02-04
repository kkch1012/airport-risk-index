"""
질병관리청 검역관리지역정보 API 수집기

API: 질병관리청_검역관리지역정보
발급: https://www.data.go.kr/data/15139251/openapi.do

검역관리지역은 검역감염병이 유행하거나 유행할 우려가 있어
국내로 유입될 가능성이 있는 지역으로서 검역법 제5조에 따라 지정된 지역입니다.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.collectors.base import BaseCollector
from app.config import settings


class HealthRiskCollector(BaseCollector):
    """질병관리청 검역관리지역정보 API 수집기"""

    name = "health_risk"
    source_name = "질병관리청"
    source_url = "https://apis.data.go.kr/1790387/QuarantineRegion"
    collection_interval = 21600  # 6시간

    # 검역감염병 코드 매핑 (위험도 점수 포함)
    DISEASE_CODES = {
        "MPOX": {"name": "엠폭스", "risk_score": 60},
        "CHOLERA": {"name": "콜레라", "risk_score": 70},
        "PLAGUE": {"name": "페스트", "risk_score": 90},
        "YELLOWFEVER": {"name": "황열", "risk_score": 80},
        "EBOLA": {"name": "에볼라", "risk_score": 95},
        "MERS": {"name": "중동호흡기증후군", "risk_score": 85},
        "COVID19": {"name": "코로나19", "risk_score": 50},
        "DENGUE": {"name": "뎅기열", "risk_score": 55},
        "ZIKA": {"name": "지카바이러스", "risk_score": 60},
        "MALARIA": {"name": "말라리아", "risk_score": 50},
        "CHIKUNGUNYA": {"name": "치쿤구니야열", "risk_score": 55},
        "AVIANFLU": {"name": "조류인플루엔자", "risk_score": 75},
        "POLIOVIRUS": {"name": "폴리오", "risk_score": 80},
        "LASSAFEVER": {"name": "라싸열", "risk_score": 90},
        "MARBURG": {"name": "마버그열", "risk_score": 95},
    }

    # 질병 이름으로 코드 찾기 (한글 이름 매핑)
    DISEASE_NAME_MAP = {
        "엠폭스": "MPOX",
        "원숭이두창": "MPOX",
        "콜레라": "CHOLERA",
        "페스트": "PLAGUE",
        "황열": "YELLOWFEVER",
        "에볼라바이러스병": "EBOLA",
        "에볼라": "EBOLA",
        "중동호흡기증후군": "MERS",
        "메르스": "MERS",
        "MERS": "MERS",
        "코로나바이러스감염증-19": "COVID19",
        "코로나19": "COVID19",
        "COVID-19": "COVID19",
        "뎅기열": "DENGUE",
        "지카바이러스감염증": "ZIKA",
        "지카": "ZIKA",
        "말라리아": "MALARIA",
        "치쿤구니야열": "CHIKUNGUNYA",
        "조류인플루엔자인체감염증": "AVIANFLU",
        "조류인플루엔자": "AVIANFLU",
        "H5N1": "AVIANFLU",
        "H7N9": "AVIANFLU",
        "폴리오": "POLIOVIRUS",
        "급성회백수염": "POLIOVIRUS",
        "라싸열": "LASSAFEVER",
        "마버그열": "MARBURG",
        "마버그": "MARBURG",
    }

    # 한국 공항에서 직항 노선이 있는 주요 국가들 (ISO 코드)
    TARGET_COUNTRIES = {
        "JP": "일본", "CN": "중국", "TW": "대만", "HK": "홍콩", "MO": "마카오",
        "VN": "베트남", "TH": "태국", "PH": "필리핀", "SG": "싱가포르",
        "MY": "말레이시아", "ID": "인도네시아", "KH": "캄보디아", "LA": "라오스",
        "MM": "미얀마", "IN": "인도", "NP": "네팔", "LK": "스리랑카",
        "AU": "호주", "NZ": "뉴질랜드", "GU": "괌", "FJ": "피지", "PW": "팔라우",
        "US": "미국", "CA": "캐나다", "MX": "멕시코", "BR": "브라질",
        "GB": "영국", "FR": "프랑스", "DE": "독일", "IT": "이탈리아",
        "ES": "스페인", "NL": "네덜란드", "CH": "스위스", "AT": "오스트리아",
        "CZ": "체코", "PL": "폴란드", "RU": "러시아", "TR": "튀르키예",
        "AE": "아랍에미리트", "QA": "카타르", "UZ": "우즈베키스탄", "KZ": "카자흐스탄",
        "EG": "이집트", "ET": "에티오피아", "KE": "케냐", "ZA": "남아프리카공화국",
        "MN": "몽골",
    }

    # 국가명 → ISO 코드 변환 (API 응답에서 국가명으로 오는 경우 대비)
    COUNTRY_NAME_TO_ISO = {
        "일본": "JP", "중국": "CN", "대만": "TW", "홍콩": "HK", "마카오": "MO",
        "베트남": "VN", "태국": "TH", "필리핀": "PH", "싱가포르": "SG",
        "말레이시아": "MY", "인도네시아": "ID", "캄보디아": "KH", "라오스": "LA",
        "미얀마": "MM", "인도": "IN", "네팔": "NP", "스리랑카": "LK",
        "호주": "AU", "뉴질랜드": "NZ", "괌": "GU", "피지": "FJ", "팔라우": "PW",
        "미국": "US", "캐나다": "CA", "멕시코": "MX", "브라질": "BR",
        "영국": "GB", "프랑스": "FR", "독일": "DE", "이탈리아": "IT",
        "스페인": "ES", "네덜란드": "NL", "스위스": "CH", "오스트리아": "AT",
        "체코": "CZ", "폴란드": "PL", "러시아": "RU", "튀르키예": "TR",
        "터키": "TR", "아랍에미리트": "AE", "UAE": "AE", "카타르": "QA",
        "우즈베키스탄": "UZ", "카자흐스탄": "KZ",
        "이집트": "EG", "에티오피아": "ET", "케냐": "KE", "남아프리카공화국": "ZA",
        "몽골": "MN", "대한민국": "KR", "한국": "KR",
        # 아프리카 추가 (감염병 발생 빈도 높음)
        "콩고민주공화국": "CD", "콩고": "CD", "나이지리아": "NG", "가나": "GH",
        "수단": "SD", "우간다": "UG", "탄자니아": "TZ", "소말리아": "SO",
        "기니": "GN", "라이베리아": "LR", "시에라리온": "SL", "말리": "ML",
        # 중남미 추가
        "콜롬비아": "CO", "페루": "PE", "에콰도르": "EC", "볼리비아": "BO",
        "아르헨티나": "AR", "파라과이": "PY",
        # 아시아 추가
        "파키스탄": "PK", "방글라데시": "BD", "아프가니스탄": "AF",
    }

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or settings.DATA_GO_KR_API_KEY

    async def _fetch_quarantine_regions(
        self,
        page: int = 1,
        per_page: int = 100,
        use_yn: str = "Y"
    ) -> Dict[str, Any]:
        """
        검역관리지역 목록 조회

        Args:
            page: 페이지 번호
            per_page: 페이지당 결과 수
            use_yn: 사용여부 (Y: 현재 유효한 지역만)

        Returns:
            API 응답 데이터
        """
        params = {
            "serviceKey": self.api_key,
            "pageNo": str(page),
            "numOfRows": str(per_page),
            "resType": "2",  # JSON
            "useYn": use_yn,
        }

        url = f"{self.source_url}/NationDisease?{urlencode(params, safe='=')}"

        try:
            response = await self.client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"검역관리지역 조회 실패: {e}")
            raise

    async def collect(self) -> List[Dict[str, Any]]:
        """검역관리지역 데이터 수집"""
        if not self.api_key:
            self.logger.warning("API 키가 설정되지 않았습니다. 목업 데이터를 반환합니다.")
            return self._get_mock_data()

        results = []
        page = 1

        while True:
            try:
                response = await self._fetch_quarantine_regions(page=page, per_page=100)

                # 응답 구조 파싱
                body = response.get("body", response)
                items = body.get("items", [])

                if not items:
                    # 응답 구조가 다를 수 있음
                    if isinstance(response, list):
                        items = response
                    else:
                        items = response.get("data", [])

                if not items:
                    break

                for item in items:
                    # 국가명 추출 및 ISO 코드 변환
                    country_name = item.get("ntnNm", "") or item.get("nation_nm", "") or item.get("국가", "")
                    country_code = self._get_country_code(country_name)

                    # 질병명 추출
                    disease_name = (
                        item.get("icdNm", "") or
                        item.get("disease_nm", "") or
                        item.get("검역감염병", "")
                    )

                    results.append({
                        "country_name": country_name,
                        "country_code": country_code,
                        "disease_name": disease_name,
                        "disease_code": self._get_disease_code(disease_name),
                        "designation_date": (
                            item.get("srvlncBgngYmd", "") or
                            item.get("지정일자", "")
                        ),
                        "release_date": (
                            item.get("srvlncEndYmd", "") or
                            item.get("해지일자", "")
                        ),
                        "is_active": item.get("useYn", "Y") == "Y" or item.get("지속여부", "Y") == "Y",
                        "risk_group": item.get("riskGroupNm", ""),
                        "collected_at": datetime.now().isoformat(),
                    })

                # 다음 페이지 확인
                total_count = body.get("totalCount", 0)
                if len(results) >= total_count or len(items) < 100:
                    break
                page += 1

            except Exception as e:
                self.logger.error(f"페이지 {page} 수집 실패: {e}")
                # API 키 오류 등의 경우 목업 데이터로 대체
                if not results:
                    return self._get_mock_data()
                break

        self.logger.info(f"검역관리지역 {len(results)}건 수집 완료")
        return results if results else self._get_mock_data()

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        수집된 데이터를 표준 형식으로 변환

        Args:
            raw_data: 수집된 원시 데이터

        Returns:
            변환된 검역관리지역 데이터
        """
        disease_code = raw_data.get("disease_code", "")
        disease_info = self.DISEASE_CODES.get(disease_code, {"name": raw_data.get("disease_name", ""), "risk_score": 50})

        # 질병별 기본 위험도
        base_risk_score = disease_info.get("risk_score", 50)

        # 지정일 기준 경과일에 따른 가중치 (최근일수록 위험도 증가)
        designation_date = raw_data.get("designation_date", "")
        recency_factor = self._calculate_recency_factor(designation_date)

        # 최종 위험점수 계산
        risk_score = min(100, base_risk_score * recency_factor)

        return {
            "country_code": raw_data.get("country_code", ""),
            "country_name": raw_data.get("country_name", ""),
            "disease_code": disease_code,
            "disease_name": disease_info.get("name", raw_data.get("disease_name", "")),
            "designation_date": designation_date,
            "release_date": raw_data.get("release_date", ""),
            "is_active": raw_data.get("is_active", True),
            "risk_score": round(risk_score, 1),
            "risk_group": raw_data.get("risk_group", ""),
            "collected_at": raw_data.get("collected_at", ""),
            "source": self.source_name,
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        # 국가명 또는 국가코드 필수
        if not data.get("country_name") and not data.get("country_code"):
            return False

        # 질병명 필수
        if not data.get("disease_name"):
            return False

        # 위험점수 범위 확인
        risk_score = data.get("risk_score", -1)
        if risk_score < 0 or risk_score > 100:
            return False

        return True

    def _get_country_code(self, country_name: str) -> str:
        """국가명을 ISO 코드로 변환"""
        if not country_name:
            return ""

        # 직접 매핑 시도
        code = self.COUNTRY_NAME_TO_ISO.get(country_name, "")
        if code:
            return code

        # 부분 매칭 시도
        for name, iso_code in self.COUNTRY_NAME_TO_ISO.items():
            if name in country_name or country_name in name:
                return iso_code

        return ""

    def _get_disease_code(self, disease_name: str) -> str:
        """질병명을 코드로 변환"""
        if not disease_name:
            return ""

        # 직접 매핑 시도
        code = self.DISEASE_NAME_MAP.get(disease_name, "")
        if code:
            return code

        # 부분 매칭 시도
        disease_name_upper = disease_name.upper()
        for name, code in self.DISEASE_NAME_MAP.items():
            if name.upper() in disease_name_upper or disease_name_upper in name.upper():
                return code

        return "UNKNOWN"

    def _calculate_recency_factor(self, designation_date: str) -> float:
        """
        지정일 기준 경과일에 따른 가중치 계산
        최근 지정일수록 높은 가중치 반환

        Args:
            designation_date: 지정일자 (YYYY-MM-DD 또는 YYYYMMDD)

        Returns:
            가중치 (0.8 ~ 1.2)
        """
        if not designation_date:
            return 1.0

        try:
            # 날짜 형식 파싱
            if "-" in designation_date:
                date_obj = datetime.strptime(designation_date[:10], "%Y-%m-%d")
            else:
                date_obj = datetime.strptime(designation_date[:8], "%Y%m%d")

            days_ago = (datetime.now() - date_obj).days

            # 30일 이내: 1.2배, 90일 이내: 1.1배, 180일 이내: 1.0배, 그 이상: 0.9배
            if days_ago <= 30:
                return 1.2
            elif days_ago <= 90:
                return 1.1
            elif days_ago <= 180:
                return 1.0
            else:
                return 0.9

        except (ValueError, TypeError):
            return 1.0

    def _get_mock_data(self) -> List[Dict[str, Any]]:
        """API 키 없을 때 사용할 목업 데이터"""
        import random

        now = datetime.now()
        random.seed(now.strftime("%Y%m%d"))

        mock_results = []

        # 실제 검역관리지역과 유사한 목업 데이터
        mock_quarantine_data = [
            # 아프리카 - 에볼라, 콜레라 등
            {"country": "콩고민주공화국", "disease": "에볼라바이러스병", "risk": 85},
            {"country": "기니", "disease": "에볼라바이러스병", "risk": 75},
            {"country": "우간다", "disease": "에볼라바이러스병", "risk": 70},
            # 동남아 - 뎅기열, 지카, 콜레라
            {"country": "필리핀", "disease": "콜레라", "risk": 55},
            {"country": "인도네시아", "disease": "뎅기열", "risk": 45},
            {"country": "베트남", "disease": "뎅기열", "risk": 40},
            {"country": "태국", "disease": "뎅기열", "risk": 40},
            # 중동 - MERS
            {"country": "아랍에미리트", "disease": "중동호흡기증후군", "risk": 50},
            {"country": "카타르", "disease": "중동호흡기증후군", "risk": 45},
            # 남미 - 황열, 지카
            {"country": "브라질", "disease": "황열", "risk": 55},
            {"country": "브라질", "disease": "지카바이러스감염증", "risk": 50},
            # 아시아 - 엠폭스
            {"country": "일본", "disease": "엠폭스", "risk": 35},
            {"country": "중국", "disease": "엠폭스", "risk": 40},
            # 아프리카 추가
            {"country": "나이지리아", "disease": "콜레라", "risk": 60},
            {"country": "에티오피아", "disease": "콜레라", "risk": 55},
            # 조류인플루엔자
            {"country": "중국", "disease": "조류인플루엔자인체감염증", "risk": 50},
        ]

        for item in mock_quarantine_data:
            country_code = self._get_country_code(item["country"])
            disease_code = self._get_disease_code(item["disease"])

            # 약간의 랜덤 변동
            risk_variation = random.uniform(-5, 5)
            risk_score = max(0, min(100, item["risk"] + risk_variation))

            mock_results.append({
                "country_name": item["country"],
                "country_code": country_code,
                "disease_name": item["disease"],
                "disease_code": disease_code,
                "designation_date": (now.replace(day=1)).strftime("%Y-%m-%d"),
                "release_date": "",
                "is_active": True,
                "risk_group": "",
                "collected_at": now.isoformat(),
            })

        return mock_results

    def get_summary(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        수집된 데이터의 요약 통계

        Args:
            data_list: 변환된 데이터 리스트

        Returns:
            요약 통계
        """
        disease_counts = {}
        country_risk_map = {}
        high_risk_regions = []

        for data in data_list:
            # 질병별 카운트
            disease = data.get("disease_name", "Unknown")
            disease_counts[disease] = disease_counts.get(disease, 0) + 1

            # 국가별 최대 위험도 (여러 질병이 있을 수 있음)
            country = data.get("country_code") or data.get("country_name", "")
            risk_score = data.get("risk_score", 0)

            if country:
                current_risk = country_risk_map.get(country, 0)
                country_risk_map[country] = max(current_risk, risk_score)

            # 고위험 지역 (60점 이상)
            if risk_score >= 60:
                high_risk_regions.append({
                    "country": data.get("country_name", ""),
                    "country_code": data.get("country_code", ""),
                    "disease": disease,
                    "risk_score": risk_score,
                })

        # 평균 위험도 계산
        risk_scores = [d.get("risk_score", 0) for d in data_list if d.get("risk_score")]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0

        return {
            "total_quarantine_regions": len(data_list),
            "disease_distribution": disease_counts,
            "high_risk_regions": sorted(high_risk_regions, key=lambda x: x["risk_score"], reverse=True)[:10],
            "average_risk_score": round(avg_risk, 1),
            "countries_with_quarantine": len(country_risk_map),
            "country_risk_summary": country_risk_map,
        }

    def calculate_airport_health_risk(
        self,
        airport_code: str,
        data_list: List[Dict[str, Any]],
        airport_routes: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        특정 공항의 보건위험 점수 계산

        Args:
            airport_code: 공항 코드
            data_list: 검역관리지역 데이터 리스트
            airport_routes: 공항별 취항 국가 코드 목록

        Returns:
            공항 보건위험 점수 및 상세 정보
        """
        # 해당 공항의 취항 국가
        route_countries = airport_routes.get(airport_code, [])

        if not route_countries:
            return {
                "airport_code": airport_code,
                "health_risk_score": 5.0,
                "risk_level": "LOW",
                "affected_routes": [],
                "message": "국제선 노선 없음",
            }

        # 취항 국가 중 검역관리지역 필터링
        affected_routes = []
        country_scores = []

        # 국가별 위험도 맵 생성
        country_risk_map = {}
        for data in data_list:
            country_code = data.get("country_code", "")
            if country_code:
                risk_score = data.get("risk_score", 0)
                disease = data.get("disease_name", "")

                if country_code not in country_risk_map:
                    country_risk_map[country_code] = {"max_risk": 0, "diseases": []}

                country_risk_map[country_code]["max_risk"] = max(
                    country_risk_map[country_code]["max_risk"],
                    risk_score
                )
                country_risk_map[country_code]["diseases"].append({
                    "name": disease,
                    "risk_score": risk_score,
                })

        # 취항 국가별 위험도 수집
        for country_code in route_countries:
            if country_code in country_risk_map:
                info = country_risk_map[country_code]
                country_scores.append(info["max_risk"])
                affected_routes.append({
                    "country_code": country_code,
                    "country_name": self.TARGET_COUNTRIES.get(country_code, country_code),
                    "risk_score": info["max_risk"],
                    "diseases": info["diseases"],
                })
            else:
                country_scores.append(0)

        # 최종 점수 계산 (최대값 70% + 평균 30%)
        if country_scores:
            max_score = max(country_scores)
            avg_score = sum(country_scores) / len(country_scores)
            final_score = max_score * 0.7 + avg_score * 0.3
        else:
            final_score = 0

        # 위험등급 판정
        if final_score < 25:
            risk_level = "LOW"
        elif final_score < 50:
            risk_level = "MODERATE"
        elif final_score < 75:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"

        return {
            "airport_code": airport_code,
            "health_risk_score": round(final_score, 2),
            "risk_level": risk_level,
            "affected_routes": sorted(affected_routes, key=lambda x: x["risk_score"], reverse=True),
            "total_routes_checked": len(route_countries),
            "routes_with_quarantine": len(affected_routes),
        }
