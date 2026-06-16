"""
보안위협 데이터 수집기

다중 소스:
1. Google News RSS 보안 키워드 탐지 (뉴스 크롤러 재활용)
2. 관세청 밀수단속 현황 API (data.go.kr)
3. 법무부 출입국 통계 API (data.go.kr)

API 실패 시 mock fallback (기존 수집기 패턴 동일)
"""

import re
import defusedxml.ElementTree as ET
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List
from urllib.parse import quote, urlencode

from app.collectors.base import BaseCollector
from app.config import settings

# 보안 관련 키워드 (뉴스 탐지용)
SECURITY_KEYWORDS = {
    "terror": ["테러", "폭발물", "폭탄", "총기", "위협", "협박"],
    "smuggling": ["밀수", "밀반입", "밀반출", "마약", "금지품", "적발"],
    "illegal_entry": ["불법입국", "불법체류", "밀입국", "위조여권", "위변조"],
}

# 키워드별 심각도 가중치
KEYWORD_SEVERITY = {
    "테러": 1.0, "폭발물": 0.9, "폭탄": 0.9, "총기": 0.8,
    "위협": 0.5, "협박": 0.5,
    "밀수": 0.6, "밀반입": 0.6, "밀반출": 0.5, "마약": 0.7,
    "금지품": 0.4, "적발": 0.3,
    "불법입국": 0.5, "불법체류": 0.4, "밀입국": 0.6,
    "위조여권": 0.7, "위변조": 0.5,
}

# 공항 키워드 → 공항코드 매핑
AIRPORT_KEYWORDS = {
    "인천공항": "ICN", "인천국제공항": "ICN",
    "김포공항": "GMP", "김포국제공항": "GMP",
    "김해공항": "PUS", "김해국제공항": "PUS",
    "제주공항": "CJU", "제주국제공항": "CJU",
    "대구공항": "TAE", "대구국제공항": "TAE",
    "청주공항": "CJJ", "청주국제공항": "CJJ",
    "광주공항": "KWJ",
    "여수공항": "RSU",
    "무안공항": "MWX", "무안국제공항": "MWX",
}


class SecurityThreatCollector(BaseCollector):
    """보안위협 데이터 수집기"""

    name = "security_threat"
    source_name = "보안위협 통합 수집"
    source_url = "https://news.google.com/rss/search"
    collection_interval = 3600  # 1시간

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or settings.DATA_GO_KR_API_KEY

    async def collect(self) -> List[Dict[str, Any]]:
        """3개 소스에서 보안 데이터 수집"""
        all_data = []

        # 1. 뉴스 기반 보안 키워드 탐지
        news_data = await self._fetch_news_security()
        all_data.extend(news_data)

        # 2. 관세청 밀수단속 API
        customs_data = await self._fetch_customs_data()
        all_data.extend(customs_data)

        # 3. 출입국 통계 API
        immigration_data = await self._fetch_immigration_data()
        all_data.extend(immigration_data)

        if not all_data:
            self.logger.warning("보안위협 수집 실패 → 데이터 없음")
            return []

        self.logger.info("보안위협 %d건 수집", len(all_data))
        return all_data

    async def _fetch_news_security(self) -> List[Dict[str, Any]]:
        """Google News RSS에서 보안 관련 뉴스 수집"""
        results = []
        queries = ["공항 테러 위협", "공항 밀수 적발", "공항 불법입국"]
        cutoff = datetime.now() - timedelta(days=7)

        for query in queries:
            try:
                query_with_date = f"{query} when:7d"
                encoded_query = quote(query_with_date)
                url = f"{self.source_url}?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

                response = await self.client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; AirportRiskMonitor/1.0)"},
                )
                response.raise_for_status()

                articles = self._parse_rss(response.text)
                for article in articles:
                    if self._is_too_old(article.get("published_at", ""), cutoff):
                        continue
                    threat_type = self._detect_threat_type(article.get("title", ""))
                    if threat_type:
                        article["source_type"] = "news"
                        article["threat_type"] = threat_type
                        results.append(article)
            except Exception as e:
                self.logger.warning("보안 뉴스 수집 실패 ('%s'): %s", query, e)
                continue

        return results

    async def _fetch_customs_data(self) -> List[Dict[str, Any]]:
        """관세청 밀수단속 현황 API"""
        if not self.api_key:
            return []

        try:
            params = {
                "serviceKey": self.api_key,
                "pageNo": "1",
                "numOfRows": "20",
                "type": "json",
            }
            url = f"https://apis.data.go.kr/1220000/SmugStatService/getSmugStat?{urlencode(params, safe='=')}"
            response = await self.client.get(url, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            items = (
                data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
            )
            if not isinstance(items, list):
                items = [items] if items else []

            results = []
            for item in items:
                results.append({
                    "source_type": "customs",
                    "threat_type": "smuggling",
                    "title": item.get("crmeNm", "밀수단속"),
                    "count": int(item.get("cnt", 0) or 0),
                    "year": item.get("yr", ""),
                    "category": item.get("crmeClNm", ""),
                    "collected_at": datetime.now().isoformat(),
                })
            return results

        except Exception as e:
            self.logger.warning("관세청 API 실패: %s", e)
            return []

    async def _fetch_immigration_data(self) -> List[Dict[str, Any]]:
        """법무부 출입국 통계 API"""
        if not self.api_key:
            return []

        try:
            params = {
                "serviceKey": self.api_key,
                "pageNo": "1",
                "numOfRows": "20",
                "type": "json",
            }
            url = f"https://apis.data.go.kr/1262000/ImmigrationStatService/getImmigrationStat?{urlencode(params, safe='=')}"
            response = await self.client.get(url, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            items = (
                data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
            )
            if not isinstance(items, list):
                items = [items] if items else []

            results = []
            for item in items:
                results.append({
                    "source_type": "immigration",
                    "threat_type": "illegal_entry",
                    "title": item.get("statNm", "출입국통계"),
                    "count": int(item.get("cnt", 0) or 0),
                    "year": item.get("yr", ""),
                    "category": item.get("statClNm", ""),
                    "collected_at": datetime.now().isoformat(),
                })
            return results

        except Exception as e:
            self.logger.warning("출입국 통계 API 실패: %s", e)
            return []

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """원시 데이터 → 표준 형식"""
        source_type = raw_data.get("source_type", "unknown")
        threat_type = raw_data.get("threat_type", "unknown")
        title = raw_data.get("title", "")

        if source_type == "news":
            score = self._calculate_news_threat_score(title)
            airport_code = self._detect_airport(title)
        else:
            # customs / immigration: 건수 기반 점수
            count = raw_data.get("count", 0)
            score = self._calculate_stat_threat_score(threat_type, count)
            airport_code = None

        return {
            "source_type": source_type,
            "threat_type": threat_type,
            "title": title,
            "score": round(min(100, max(0, score)), 1),
            "airport_code": airport_code,
            "details": raw_data,
            "collected_at": raw_data.get("collected_at", datetime.now().isoformat()),
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """유효성 검증"""
        if not data.get("threat_type"):
            return False
        score = data.get("score", -1)
        if score < 0 or score > 100:
            return False
        return True

    def _parse_rss(self, xml_text: str) -> List[Dict[str, Any]]:
        """RSS XML 파싱"""
        items = []
        try:
            root = ET.fromstring(xml_text)
            channel = root.find("channel")
            if channel is None:
                return items

            for item in channel.findall("item"):
                items.append({
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "published_at": item.findtext("pubDate", ""),
                    "source": item.findtext("source", ""),
                    "collected_at": datetime.now().isoformat(),
                })
        except ET.ParseError:
            pass
        return items

    def _is_too_old(self, date_str: str, cutoff: datetime) -> bool:
        """날짜가 cutoff 이전인지 확인"""
        if not date_str:
            return False
        for fmt in [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt < cutoff
            except ValueError:
                continue
        return False

    def _detect_threat_type(self, text: str) -> str:
        """텍스트에서 보안위협 유형 탐지"""
        best_type = ""
        max_count = 0

        for threat_type, keywords in SECURITY_KEYWORDS.items():
            found = sum(1 for kw in keywords if kw in text)
            if found > max_count:
                max_count = found
                best_type = threat_type

        return best_type

    def _detect_airport(self, text: str) -> str:
        """텍스트에서 공항 코드 탐지"""
        for keyword, code in AIRPORT_KEYWORDS.items():
            if keyword in text:
                return code
        return None

    def _calculate_news_threat_score(self, title: str) -> float:
        """뉴스 기반 위협 점수 계산"""
        score = 0.0
        for keyword, severity in KEYWORD_SEVERITY.items():
            if keyword in title:
                score += severity * 30

        # 긴급 키워드 보너스
        urgent = {"긴급", "속보", "비상", "경보"}
        for kw in urgent:
            if kw in title:
                score += 15

        return min(100, score)

    def _calculate_stat_threat_score(self, threat_type: str, count: int) -> float:
        """통계 기반 위협 점수 계산"""
        if threat_type == "smuggling":
            # 밀수: 건수에 비례, 100건 이상이면 최대
            return min(100, count * 1.0)
        elif threat_type == "illegal_entry":
            # 불법입국: 건수에 비례, 50건 이상이면 최대
            return min(100, count * 2.0)
        return 0
