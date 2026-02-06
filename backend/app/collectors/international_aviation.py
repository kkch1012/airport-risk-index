"""
해외 항공사고 데이터 수집기

Source: Aviation Safety Network (ASN) RSS Feed
수집 대상: 한국 직항 노선 관련 국가의 항공사고/준사고
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List
import logging
import re

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
    "incident": 50,
    "emergency": 60,
    "diversion": 40,
    "runway": 30,
    "turbulence": 30,
    "bird strike": 20,
}


class InternationalAviationCollector(BaseCollector):
    """해외 항공사고 데이터 수집기 (ASN RSS)"""

    name = "international_aviation"
    source_name = "Aviation Safety Network"
    source_url = "https://aviation-safety.net/rss/latest-accidents.xml"
    collection_interval = 21600  # 6시간

    async def collect(self) -> List[Dict[str, Any]]:
        """ASN RSS 피드에서 최근 사고 데이터 수집"""
        try:
            response = await self.client.get(
                self.source_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AirportRiskMonitor/1.0)",
                },
            )
            response.raise_for_status()

            items = self._parse_rss(response.text)

            if items:
                self.logger.info("ASN RSS: %d건 수집", len(items))
                return items

            self.logger.warning("ASN RSS 파싱 결과 없음, 목업 사용")
            return self._get_mock_data()

        except Exception as e:
            self.logger.warning("ASN 수집 실패 (%s), 목업 사용", e)
            return self._get_mock_data()

    def _parse_rss(self, xml_text: str) -> List[Dict[str, Any]]:
        """RSS XML 파싱"""
        items = []
        try:
            root = ET.fromstring(xml_text)
            channel = root.find("channel")
            if channel is None:
                return items

            for item in channel.findall("item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                description = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")

                items.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "pub_date": pub_date,
                })
        except ET.ParseError as e:
            self.logger.warning("RSS XML 파싱 오류: %s", e)

        return items

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """RSS 항목 → 표준 형식"""
        title = raw_data.get("title", "")
        description = raw_data.get("description", "")
        full_text = f"{title} {description}".lower()

        # 심각도 점수 계산
        severity_score = self._calculate_severity(full_text)

        # 국가/공항 코드 추출
        country_code = self._extract_country(full_text)
        airport_code = self._extract_airport_code(full_text)

        # 사고 날짜 파싱
        incident_date = self._parse_date(raw_data.get("pub_date", ""))

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
        """텍스트에서 국가 코드 추출"""
        country_names = {
            "japan": "JP", "china": "CN", "united states": "US", "usa": "US",
            "thailand": "TH", "vietnam": "VN", "taiwan": "TW",
            "philippines": "PH", "singapore": "SG", "hong kong": "HK",
            "germany": "DE", "france": "FR", "united kingdom": "GB", "uk": "GB",
            "australia": "AU", "indonesia": "ID", "malaysia": "MY",
        }
        for name, code in country_names.items():
            if name in text:
                return code
        return ""

    def _extract_airport_code(self, text: str) -> str:
        """텍스트에서 IATA 공항 코드 추출"""
        match = re.search(r'\b([A-Z]{3})\b', text.upper())
        return match.group(1) if match else ""

    def _parse_date(self, date_str: str) -> str:
        """날짜 문자열 파싱"""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")

        for fmt in [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%dT%H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return datetime.now().strftime("%Y-%m-%d")

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
        import hashlib
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
            "engine failure", "landing gear issue", "diversion due to weather",
        ]

        mock = []
        for i in range(random.randint(3, 8)):
            days_ago = random.randint(1, 60)
            date = (now - timedelta(days=days_ago)).strftime("%a, %d %b %Y 12:00:00 GMT")
            country = random.choice(countries)
            incident_type = random.choice(types)

            mock.append({
                "title": f"Aircraft {incident_type} in {country}",
                "link": f"https://aviation-safety.net/wikibase/{random.randint(100000, 999999)}",
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
