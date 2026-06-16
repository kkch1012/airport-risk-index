"""
ARAIB 항공사고 데이터 수집기

URL: https://araib.molit.go.kr/USR/airboard0201/m_34497/lst.jsp
데이터: 항공사고조사보고서 목록

항공안전 지표:
- 사고 건수
- 준사고 건수
- 사고 발생 공항
"""

import asyncio
import html as html_module
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import logging

from app.collectors.base import BaseCollector
from app.config import settings

# bs4는 선택적 import (없으면 목업 사용)
try:
    from bs4 import BeautifulSoup
    HAS_CRAWL_DEPS = True
except ImportError:
    HAS_CRAWL_DEPS = False


class AviationSafetyCollector(BaseCollector):
    """ARAIB 항공사고 데이터 수집기"""

    name = "aviation_safety"
    source_name = "항공철도사고조사위원회"
    source_url = "https://araib.molit.go.kr/USR/airboard0201/m_34497/lst.jsp"
    collection_interval = 86400  # 24시간 (사고 데이터는 자주 변하지 않음)

    # 사고 유형별 위험 점수
    ACCIDENT_TYPE_SCORES = {
        "항공기 사고": 100,
        "항공기 준사고": 70,
        "경량항공기사고": 50,
        "경량항공기 사고": 50,
        "초경량비행장치사고": 30,
        "초경량비행장치 사고": 30,
    }

    # 공항 코드 매핑 (발생위치에서 공항 추출용)
    AIRPORT_KEYWORDS = {
        "인천": "ICN",
        "김포": "GMP",
        "김해": "PUS",
        "제주": "CJU",
        "대구": "TAE",
        "청주": "CJJ",
        "광주": "KWJ",
        "여수": "RSU",
        "울산": "USN",
        "포항": "KPO",
        "원주": "WJU",
        "양양": "YNY",
        "사천": "HIN",
        "군산": "KUV",
        "무안": "MWX",
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    def __init__(self):
        super().__init__()
        self.can_crawl = HAS_CRAWL_DEPS

    async def _fetch_page(self, page_num: int = 1) -> Optional[str]:
        """페이지 HTML 가져오기 (async)"""
        params = {
            "currentPage": page_num,
            "srchKeyword": "",
        }
        try:
            response = await self.client.get(
                self.source_url,
                params=params,
                headers=self.HEADERS,
            )
            if response.status_code == 200:
                return response.text
            self.logger.warning("ARAIB fetch failed: status %d", response.status_code)
            return None
        except Exception as e:
            self.logger.warning("ARAIB fetch error: %s", e)
            return None

    def _parse_accidents(self, html: str) -> List[Dict[str, Any]]:
        """HTML에서 사고 목록 파싱"""
        soup = BeautifulSoup(html, "html.parser")
        accidents = []

        table = (
            soup.find("table", class_="tbl_list") or
            soup.find("table", class_="board_list") or
            soup.find("table")
        )

        if not table:
            return accidents

        tbody = table.find("tbody")
        rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            try:
                accident = {
                    "accident_id": cols[0].get_text(strip=True),
                    "occurrence_date": cols[1].get_text(strip=True),
                    "report_date": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    "accident_type": cols[3].get_text(strip=True) if len(cols) > 3 else "",
                    "operator": cols[4].get_text(strip=True) if len(cols) > 4 else "",
                    "aircraft_type": cols[5].get_text(strip=True) if len(cols) > 5 else "",
                    "location": cols[6].get_text(strip=True) if len(cols) > 6 else "",
                    "status": cols[7].get_text(strip=True) if len(cols) > 7 else "",
                }

                if accident["accident_id"]:
                    accidents.append(accident)

            except Exception as e:
                self.logger.warning(f"행 파싱 오류: {e}")
                continue

        return accidents

    def _get_total_pages(self, html: str) -> int:
        """총 페이지 수 추출"""
        soup = BeautifulSoup(html, "html.parser")
        pagination = (
            soup.find("div", class_="paging") or
            soup.find("div", class_="pagination") or
            soup.find("ul", class_="pagination")
        )

        if pagination:
            links = pagination.find_all("a")
            max_page = 1
            for link in links:
                text = link.get_text(strip=True)
                if text.isdigit():
                    max_page = max(max_page, int(text))
            return max_page

        return 1

    async def collect(self) -> List[Dict[str, Any]]:
        """항공사고 데이터 수집"""
        if not self.can_crawl:
            self.logger.warning("크롤링 의존성 없음. → 데이터 없음")
            return []

        try:
            all_accidents = []

            # 첫 페이지
            first_html = await self._fetch_page(1)
            if not first_html:
                return []
            total_pages = min(self._get_total_pages(first_html), 5)  # 최대 5페이지
            accidents = self._parse_accidents(first_html)
            all_accidents.extend(accidents)

            # 추가 페이지
            for page in range(2, total_pages + 1):
                await asyncio.sleep(0.3)
                try:
                    html = await self._fetch_page(page)
                    accidents = self._parse_accidents(html)
                    all_accidents.extend(accidents)
                except Exception as e:
                    self.logger.warning(f"페이지 {page} 수집 실패: {e}")

            self.logger.info(f"항공사고 {len(all_accidents)}건 수집 완료")

            if not all_accidents:
                return []

            return all_accidents

        except Exception as e:
            self.logger.error(f"크롤링 실패: {e}")
            return []

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """수집된 데이터를 표준 형식으로 변환"""
        accident_type = raw_data.get("accident_type", "")
        base_score = self.ACCIDENT_TYPE_SCORES.get(accident_type, 40)

        # 발생 위치에서 공항 코드 추출
        location = raw_data.get("location", "")
        airport_code = self._extract_airport_code(location)

        # 발생일 기준 최근 여부 확인
        occurrence_date = raw_data.get("occurrence_date", "")
        recency_factor = self._calculate_recency_factor(occurrence_date)

        risk_score = min(100, base_score * recency_factor)

        return {
            "accident_id": raw_data.get("accident_id", ""),
            "occurrence_date": occurrence_date,
            "report_date": raw_data.get("report_date", ""),
            "accident_type": accident_type,
            "operator": raw_data.get("operator", ""),
            "aircraft_type": raw_data.get("aircraft_type", ""),
            "location": location,
            "airport_code": airport_code,
            "status": raw_data.get("status", ""),
            "risk_score": round(risk_score, 1),
            "collected_at": datetime.now().isoformat(),
            "source": self.source_name,
        }

    def _extract_airport_code(self, location: str) -> str:
        """발생 위치에서 공항 코드 추출"""
        if not location:
            return ""

        for keyword, code in self.AIRPORT_KEYWORDS.items():
            if keyword in location:
                return code

        return ""

    def _calculate_recency_factor(self, date_str: str) -> float:
        """발생일 기준 최근 가중치 계산"""
        if not date_str:
            return 1.0

        try:
            # YYYY/MM/DD 형식
            date_obj = datetime.strptime(date_str.replace("-", "/"), "%Y/%m/%d")
            days_ago = (datetime.now() - date_obj).days

            if days_ago <= 30:
                return 1.5
            elif days_ago <= 90:
                return 1.3
            elif days_ago <= 180:
                return 1.1
            elif days_ago <= 365:
                return 1.0
            else:
                return 0.8

        except (ValueError, TypeError):
            return 1.0

    def validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        if not data.get("accident_id"):
            return False
        if not data.get("accident_type"):
            return False
        return True

    def get_summary(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """수집 데이터 요약"""
        if not data_list:
            return {"total_accidents": 0, "by_type": {}, "by_airport": {}}

        by_type = {}
        by_airport = {}
        recent_accidents = []

        for data in data_list:
            # 유형별 집계
            acc_type = data.get("accident_type", "기타")
            by_type[acc_type] = by_type.get(acc_type, 0) + 1

            # 공항별 집계
            airport = data.get("airport_code", "")
            if airport:
                by_airport[airport] = by_airport.get(airport, 0) + 1

            # 최근 90일 이내 사고
            try:
                occ_date = data.get("occurrence_date", "")
                if occ_date:
                    date_obj = datetime.strptime(occ_date.replace("-", "/"), "%Y/%m/%d")
                    if (datetime.now() - date_obj).days <= 90:
                        recent_accidents.append(data)
            except (ValueError, TypeError):
                pass

        return {
            "total_accidents": len(data_list),
            "by_type": by_type,
            "by_airport": by_airport,
            "recent_90days": len(recent_accidents),
            "recent_accidents": recent_accidents[:5],
        }

    def calculate_airport_aviation_score(
        self,
        airport_code: str,
        data_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """특정 공항의 항공안전 점수 계산"""
        airport_accidents = [
            d for d in data_list
            if d.get("airport_code") == airport_code
        ]

        if not airport_accidents:
            # 해당 공항 사고 없음 = 낮은 위험
            return {
                "airport_code": airport_code,
                "incident_count": 0,
                "aviation_score": 10.0,
                "risk_level": "LOW",
                "recent_incidents": [],
            }

        # 사고 건수 기반 점수
        count = len(airport_accidents)
        count_score = min(50, count * 15)

        # 사고 심각도 기반 점수
        severity_scores = [d.get("risk_score", 30) for d in airport_accidents]
        avg_severity = sum(severity_scores) / len(severity_scores)
        severity_score = avg_severity * 0.5

        final_score = min(100, count_score + severity_score)

        # 위험등급
        if final_score < 25:
            level = "LOW"
        elif final_score < 50:
            level = "MODERATE"
        elif final_score < 75:
            level = "HIGH"
        else:
            level = "CRITICAL"

        return {
            "airport_code": airport_code,
            "incident_count": count,
            "aviation_score": round(final_score, 2),
            "risk_level": level,
            "recent_incidents": airport_accidents[:3],
        }
