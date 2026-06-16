"""
뉴스 크롤링 수집기

Source: Google News RSS (한국어)
키워드 기반 공항/항공 관련 위험 뉴스 탐지
"""

import defusedxml.ElementTree as ET
import re
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote
import logging

from app.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# 위험 카테고리별 키워드
RISK_KEYWORDS = {
    "weather": ["태풍", "폭설", "강풍", "안개", "폭우", "호우", "결빙", "난기류", "황사"],
    "security": ["테러", "폭발", "위협", "불법", "밀수", "총기", "폭탄", "보안"],
    "operational": ["지연", "결항", "취소", "마비", "혼잡", "파업", "시스템장애", "활주로폐쇄"],
    "health": ["전염병", "검역", "코로나", "바이러스", "감염병", "방역", "격리", "팬데믹"],
    "aviation": ["사고", "추락", "긴급착륙", "결함", "엔진고장", "화재", "조류충돌", "준사고"],
}

# 공항 관련 키워드
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

# 검색 쿼리 (Google News RSS용)
SEARCH_QUERIES = [
    "공항 사고",
    "항공 안전",
    "공항 지연 결항",
    "항공 테러 위협",
    "공항 전염병",
    "태풍 공항",
    "항공기 결함",
]


class NewsCrawler(BaseCollector):
    """뉴스 크롤링 수집기"""

    name = "news_crawler"
    source_name = "Google News RSS"
    source_url = "https://news.google.com/rss/search"
    collection_interval = 3600  # 1시간

    async def collect(self) -> List[Dict[str, Any]]:
        """Google News RSS에서 뉴스 수집"""
        all_articles = []
        seen_ids = set()
        cutoff = datetime.now() - timedelta(days=7)

        for query in SEARCH_QUERIES:
            try:
                articles = await self._fetch_rss(query)
                for article in articles:
                    # 7일 이상 된 기사 필터링
                    if self._is_article_too_old(article, cutoff):
                        continue
                    article_id = self._generate_id(article)
                    if article_id not in seen_ids:
                        seen_ids.add(article_id)
                        article["article_id"] = article_id
                        all_articles.append(article)
            except Exception as e:
                self.logger.warning("RSS fetch failed for '%s': %s", query, e)
                continue

        if not all_articles:
            self.logger.warning("뉴스 수집 실패 → 데이터 없음")
            return []

        self.logger.info("뉴스 %d건 수집 (중복 제거 + 날짜 필터 후)", len(all_articles))
        return all_articles

    def _is_article_too_old(self, article: Dict[str, Any], cutoff: datetime) -> bool:
        """기사 날짜가 cutoff 이전인지 확인"""
        pub_date = article.get("published_at", "")
        if not pub_date:
            return False  # 날짜 없으면 일단 포함

        for fmt in [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
        ]:
            try:
                dt = datetime.strptime(pub_date.strip(), fmt)
                # timezone-aware → naive 변환 비교
                if dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return dt < cutoff
            except ValueError:
                continue

        return False  # 파싱 실패 시 일단 포함

    async def _fetch_rss(self, query: str) -> List[Dict[str, Any]]:
        """Google News RSS 피드 가져오기"""
        # 최근 7일 이내 뉴스만 검색하도록 when:7d 추가
        query_with_date = f"{query} when:7d"
        encoded_query = quote(query_with_date)
        url = f"{self.source_url}?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

        response = await self.client.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AirportRiskMonitor/1.0)"},
        )
        response.raise_for_status()

        return self._parse_rss(response.text)

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
                pub_date = item.findtext("pubDate", "")
                source = item.findtext("source", "")

                items.append({
                    "title": title,
                    "link": link,
                    "published_at": pub_date,
                    "source": source,
                })
        except ET.ParseError:
            pass

        return items

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """뉴스 데이터 → 표준 형식"""
        title = raw_data.get("title", "")

        # 카테고리 및 키워드 탐지
        category, keywords_found = self._detect_category(title)
        risk_score = self._calculate_risk_score(title, keywords_found)
        airport_code = self._detect_airport(title)

        return {
            "article_id": raw_data.get("article_id", self._generate_id(raw_data)),
            "title": title,
            "url": raw_data.get("link", ""),
            "published_at": self._parse_date(raw_data.get("published_at", "")),
            "source": raw_data.get("source", ""),
            "category": category,
            "risk_score": round(risk_score, 1),
            "keywords": keywords_found,
            "airport_code": airport_code,
            "collected_at": datetime.now().isoformat(),
        }

    def validate(self, data: Dict[str, Any]) -> bool:
        """유효성 검증: 위험 관련 키워드가 있는 뉴스만 통과"""
        return bool(data.get("keywords")) and data.get("risk_score", 0) > 0

    def _detect_category(self, text: str) -> tuple:
        """텍스트에서 위험 카테고리 탐지"""
        best_category = "general"
        best_keywords = []
        max_count = 0

        for category, keywords in RISK_KEYWORDS.items():
            found = [kw for kw in keywords if kw in text]
            if len(found) > max_count:
                max_count = len(found)
                best_category = category
                best_keywords = found

        return best_category, best_keywords

    def _calculate_risk_score(self, title: str, keywords_found: List[str]) -> float:
        """뉴스 위험 점수 계산"""
        if not keywords_found:
            return 0.0

        # 기본 점수: 키워드 수 기반
        base_score = min(50, len(keywords_found) * 20)

        # 긴급도 키워드 가중치
        urgent_keywords = {"긴급", "속보", "주의", "경보", "사고", "추락", "폭발"}
        urgency_bonus = sum(15 for kw in urgent_keywords if kw in title)

        # 부정어 강화
        negative_words = {"심각", "최악", "대규모", "대형", "비상"}
        negative_bonus = sum(10 for kw in negative_words if kw in title)

        return min(100, base_score + urgency_bonus + negative_bonus)

    def _detect_airport(self, text: str) -> Optional[str]:
        """텍스트에서 공항 코드 탐지"""
        for keyword, code in AIRPORT_KEYWORDS.items():
            if keyword in text:
                return code
        return None

    def _parse_date(self, date_str: str) -> str:
        """날짜 파싱"""
        if not date_str:
            return datetime.now().isoformat()

        for fmt in [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.isoformat()
            except ValueError:
                continue

        return datetime.now().isoformat()

    @staticmethod
    def _generate_id(raw_data: Dict[str, Any]) -> str:
        """고유 ID 생성"""
        content = f"{raw_data.get('title', '')}{raw_data.get('link', '')}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
