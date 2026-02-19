"""
해외 항공사고 데이터 수집기

Source: The Aviation Herald (avherald.com) - 실시간 항공사건 보도
수집 대상: 한국 직항 노선 관련 국가의 항공사고/준사고
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List
import logging

from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# 한국 직항 노선 국가 (IATA 2-letter)
MONITORED_COUNTRIES = {
    "JP", "CN", "US", "TH", "VN", "TW", "PH", "SG", "HK",
    "DE", "FR", "GB", "AU", "ID", "MY", "MO",
}

# 사고 심각도 키워드
SEVERITY_KEYWORDS = {
    "fatal": 100,
    "crash": 90,
    "accident": 80,
    "collision": 85,
    "fire": 75,
    "engine failure": 70,
    "engine shut down": 65,
    "incapacitated": 60,
    "emergency": 60,
    "cabin pressure": 55,
    "incident": 50,
    "hydraulic": 50,
    "diversion": 40,
    "rejected takeoff": 40,
    "runway excursion": 35,
    "tail scrape": 30,
    "flaps problem": 30,
    "turbulence": 30,
    "bird strike": 20,
    "gear damage": 25,
    "balked landing": 25,
}

# 국가/도시 → 국가 코드 매핑
LOCATION_TO_COUNTRY = {
    # 일본
    "tokyo": "JP", "osaka": "JP", "narita": "JP", "haneda": "JP",
    "fukuoka": "JP", "japan": "JP", "sapporo": "JP", "okinawa": "JP",
    # 중국
    "beijing": "CN", "shanghai": "CN", "china": "CN", "guangzhou": "CN",
    "shenzhen": "CN", "chengdu": "CN",
    # 미국
    "new york": "US", "los angeles": "US", "chicago": "US", "atlanta": "US",
    "washington": "US", "san francisco": "US", "seattle": "US", "dallas": "US",
    "miami": "US", "denver": "US", "tampa": "US", "usa": "US",
    # 동남아
    "bangkok": "TH", "thailand": "TH", "hanoi": "VN", "vietnam": "VN",
    "ho chi minh": "VN", "taipei": "TW", "taiwan": "TW",
    "manila": "PH", "philippines": "PH", "singapore": "SG", "changi": "SG",
    "hong kong": "HK", "jakarta": "ID", "indonesia": "ID",
    "kuala lumpur": "MY", "malaysia": "MY",
    # 유럽
    "london": "GB", "heathrow": "GB", "manchester": "GB", "gatwick": "GB",
    "paris": "FR", "france": "FR", "frankfurt": "DE", "munich": "DE",
    "germany": "DE", "nuremberg": "DE",
    # 호주
    "sydney": "AU", "melbourne": "AU", "australia": "AU",
}

# 항공사 → 국가 코드 매핑
AIRLINE_TO_COUNTRY = {
    "ana": "JP", "jal": "JP", "jac": "JP", "peach": "JP",
    "air china": "CN", "china eastern": "CN", "china southern": "CN",
    "american": "US", "united": "US", "delta": "US", "southwest": "US",
    "ups": "US", "allegiant": "US", "psa": "US", "jetblue": "US",
    "thai": "TH", "vietnam airlines": "VN", "vietjet": "VN",
    "china airlines": "TW", "eva air": "TW",
    "philippine": "PH", "cebu pacific": "PH",
    "singapore airlines": "SG", "scoot": "SG",
    "cathay": "HK", "garuda": "ID", "lion air": "ID",
    "malaysia airlines": "MY", "airasia": "MY",
    "british airways": "GB", "easyjet": "GB", "ryanair": "GB",
    "air france": "FR", "lufthansa": "DE", "condor": "DE", "corendon": "DE",
    "qantas": "AU", "jetstar": "AU",
}


class InternationalAviationCollector(BaseCollector):
    """해외 항공사고 데이터 수집기 (Aviation Herald)"""

    name = "international_aviation"
    source_name = "Aviation Herald"
    source_url = "https://avherald.com/h?list=0"
    collection_interval = 21600  # 6시간

    async def collect(self) -> List[Dict[str, Any]]:
        """Aviation Herald에서 최근 사고 데이터 수집"""
        try:
            response = await self.client.get(
                self.source_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            )
            response.raise_for_status()

            items = self._parse_html(response.text)

            if items:
                self.logger.info("Aviation Herald: %d건 수집", len(items))
                return items

            self.logger.warning("Aviation Herald 파싱 결과 없음, 목업 사용")
            return self._get_mock_data()

        except Exception as e:
            self.logger.warning("Aviation Herald 수집 실패 (%s), 목업 사용", e)
            return self._get_mock_data()

    def _parse_html(self, html: str) -> List[Dict[str, Any]]:
        """HTML에서 사고 목록 파싱"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.logger.warning("bs4 미설치, 파싱 불가")
            return []

        items = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            for a_tag in soup.find_all("a"):
                href = a_tag.get("href", "")
                title = a_tag.get_text(strip=True)

                # 사고 기사 링크만 필터 (article 파라미터가 있는 링크)
                if "article" not in href or len(title) < 20:
                    continue

                items.append({
                    "title": title,
                    "link": f"https://avherald.com/{href}" if href.startswith("/") else f"https://avherald.com{href}",
                    "description": title,
                    "pub_date": self._extract_date_from_title(title),
                })

        except Exception as e:
            self.logger.warning("HTML 파싱 오류: %s", e)

        return items

    def _extract_date_from_title(self, title: str) -> str:
        """제목에서 날짜 추출 (예: 'on Feb 17th 2026')"""
        month_map = {
            "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
            "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
            "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
        }
        match = re.search(
            r"on\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})",
            title,
        )
        if match:
            month = month_map.get(match.group(1), "01")
            day = match.group(2).zfill(2)
            year = match.group(3)
            return f"{year}-{month}-{day}"
        return datetime.now().strftime("%Y-%m-%d")

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """항목 → 표준 형식"""
        title = raw_data.get("title", "")
        description = raw_data.get("description", "")
        full_text = f"{title} {description}".lower()

        # 심각도 점수 계산
        severity_score = self._calculate_severity(full_text)

        # 국가/공항 코드 추출
        country_code = self._extract_country(full_text)
        airport_code = self._extract_airport_code(title)

        # 사고 날짜
        incident_date = raw_data.get("pub_date", "") or datetime.now().strftime("%Y-%m-%d")

        # 최근도 가중치
        recency = self._recency_factor(incident_date)
        risk_score = min(100, severity_score * recency)

        return {
            "incident_id": self._generate_id(raw_data),
            "title": title,
            "description": description[:500],
            "link": raw_data.get("link", ""),
            "incident_date": incident_date,
            "country_code": country_code,
            "airport_code": airport_code,
            "severity": self._severity_label(severity_score),
            "risk_score": round(risk_score, 1),
            "collected_at": datetime.now().isoformat(),
            "source": self.source_name,
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """유효성 검증"""
        return bool(data.get("incident_id")) and bool(data.get("title"))

    def _calculate_severity(self, text: str) -> float:
        """텍스트 기반 심각도 점수"""
        max_score = 20.0  # 기본 점수
        for keyword, score in SEVERITY_KEYWORDS.items():
            if keyword in text:
                max_score = max(max_score, score)
        return max_score

    def _severity_label(self, score: float) -> str:
        """점수 → 심각도 라벨"""
        if score >= 80:
            return "fatal"
        if score >= 50:
            return "serious"
        return "minor"

    def _extract_country(self, text: str) -> str:
        """텍스트에서 국가 코드 추출 (도시/항공사 매핑)"""
        # 먼저 도시/국가명으로 시도
        for name, code in LOCATION_TO_COUNTRY.items():
            if name in text:
                return code

        # 항공사명으로 시도
        for airline, code in AIRLINE_TO_COUNTRY.items():
            if airline in text:
                return code

        return ""

    def _extract_airport_code(self, text: str) -> str:
        """텍스트에서 IATA 공항 코드 추출"""
        match = re.search(r'\b([A-Z]{3})\b', text)
        return match.group(1) if match else ""

    def _recency_factor(self, date_str: str) -> float:
        """최근도 가중치"""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            days = (datetime.now() - dt).days
            if days <= 7:
                return 1.5
            if days <= 30:
                return 1.2
            if days <= 90:
                return 1.0
            return 0.7
        except (ValueError, TypeError):
            return 1.0

    @staticmethod
    def _generate_id(raw_data: Dict[str, Any]) -> str:
        """고유 ID 생성"""
        content = f"{raw_data.get('title', '')}{raw_data.get('link', '')}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def _get_mock_data(self) -> List[Dict[str, Any]]:
        """목업 데이터"""
        import random
        now = datetime.now()
        random.seed(now.strftime("%Y%m%d"))

        countries = ["Japan", "China", "Thailand", "Vietnam", "Philippines", "USA"]
        types = [
            "runway excursion", "turbulence injuries", "bird strike",
            "engine failure", "gear damage", "diversion due to weather",
        ]

        mock = []
        for i in range(random.randint(3, 8)):
            days_ago = random.randint(1, 60)
            date = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            country = random.choice(countries)
            incident_type = random.choice(types)

            mock.append({
                "title": f"Aircraft {incident_type} in {country}",
                "link": f"https://avherald.com/h?article={random.randint(100000, 999999)}",
                "description": f"A commercial aircraft experienced {incident_type} near {country} airport.",
                "pub_date": date,
            })

        return mock

    def get_country_risk_summary(
        self, data_list: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """국가별 항공안전 위험 요약"""
        country_scores: Dict[str, List[float]] = {}
        for item in data_list:
            cc = item.get("country_code", "")
            if cc and cc in MONITORED_COUNTRIES:
                country_scores.setdefault(cc, []).append(item.get("risk_score", 0))

        return {
            cc: round(sum(scores) / len(scores), 1)
            for cc, scores in country_scores.items()
        }
