"""
한국공항공사 항공기 운항정보 API 수집기

API: 한국공항공사_항공기 운항정보 / 실시간 항공운항 현황 정보 상세 조회
발급: https://www.data.go.kr/data/15000126/openapi.do
      https://www.data.go.kr/data/15113771/openapi.do

운영위험 지표:
- 지연율: 예정시각 대비 변경시각의 지연 비율
- 결항율: 전체 운항 대비 결항 비율
- 혼잡도: 시간대별 운항 편수
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, quote

import defusedxml.ElementTree as ET

from app.collectors.base import BaseCollector
from app.config import settings


class FlightStatusCollector(BaseCollector):
    """한국공항공사 항공기 운항정보 API 수집기"""

    name = "flight_status"
    source_name = "한국공항공사"
    source_url = "http://openapi.airport.co.kr/service/rest/FlightStatusList"
    collection_interval = 1800  # 30분

    # 국내 공항 코드 (한국공항공사 관할)
    DOMESTIC_AIRPORTS = {
        "GMP": "김포",
        "PUS": "김해",
        "CJU": "제주",
        "TAE": "대구",
        "CJJ": "청주",
        "KWJ": "광주",
        "RSU": "여수",
        "USN": "울산",
        "KPO": "포항",
        "WJU": "원주",
        "YNY": "양양",
        "HIN": "사천",
        "KUV": "군산",
        "MWX": "무안",
    }

    # 운항 상태 코드 매핑
    FLIGHT_STATUS = {
        "": {"status": "scheduled", "name": "예정", "risk_factor": 0},
        "출발": {"status": "departed", "name": "출발", "risk_factor": 0},
        "도착": {"status": "arrived", "name": "도착", "risk_factor": 0},
        "지연": {"status": "delayed", "name": "지연", "risk_factor": 30},
        "결항": {"status": "cancelled", "name": "결항", "risk_factor": 80},
        "회항": {"status": "diverted", "name": "회항", "risk_factor": 60},
        "탑승중": {"status": "boarding", "name": "탑승중", "risk_factor": 0},
        "탑승마감": {"status": "gate_closed", "name": "탑승마감", "risk_factor": 0},
    }

    # 지연 원인 분류
    DELAY_REASONS = {
        "weather": {"name": "기상", "risk_score": 40},
        "aircraft": {"name": "항공기", "risk_score": 50},
        "connection": {"name": "연결편", "risk_score": 30},
        "maintenance": {"name": "정비", "risk_score": 60},
        "congestion": {"name": "혼잡", "risk_score": 35},
        "security": {"name": "보안", "risk_score": 70},
        "other": {"name": "기타", "risk_score": 25},
    }

    def __init__(self, api_key: str = None):
        super().__init__()
        self.api_key = api_key or settings.DATA_GO_KR_API_KEY

    async def _fetch_departures(
        self,
        airport_code: str,
        search_date: str = None
    ) -> Dict[str, Any]:
        """
        출발편 운항정보 조회

        Args:
            airport_code: 공항 코드
            search_date: 조회 날짜 (YYYYMMDD)

        Returns:
            API 응답 데이터
        """
        if not search_date:
            search_date = datetime.now().strftime("%Y%m%d")

        params = {
            "serviceKey": self.api_key,
            "schDprtDate": search_date,
            "schArrvDate": search_date,
            "schAirCode": airport_code,
            "schLineType": "",  # 국내선/국제선 구분 (빈값: 전체)
            "schIOType": "D",   # D: 출발, A: 도착
            "pageNo": "1",
            "numOfRows": "500",
            "_type": "json",
        }

        url = f"{self.source_url}/getDflightStatusList?{urlencode(params, safe='=')}"

        try:
            response = await self.client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"출발편 조회 실패 ({airport_code}): {e}")
            raise

    async def _fetch_arrivals(
        self,
        airport_code: str,
        search_date: str = None
    ) -> Dict[str, Any]:
        """
        도착편 운항정보 조회

        Args:
            airport_code: 공항 코드
            search_date: 조회 날짜 (YYYYMMDD)

        Returns:
            API 응답 데이터
        """
        if not search_date:
            search_date = datetime.now().strftime("%Y%m%d")

        params = {
            "serviceKey": self.api_key,
            "schDprtDate": search_date,
            "schArrvDate": search_date,
            "schAirCode": airport_code,
            "schLineType": "",
            "schIOType": "A",   # A: 도착
            "pageNo": "1",
            "numOfRows": "500",
            "_type": "json",
        }

        url = f"{self.source_url}/getDflightStatusList?{urlencode(params, safe='=')}"

        try:
            response = await self.client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"도착편 조회 실패 ({airport_code}): {e}")
            raise

    async def collect(self) -> List[Dict[str, Any]]:
        """모든 공항의 운항정보 수집.

        한국공항공사(data.go.kr) 키가 있으면 실시간 운항현황을 사용하고,
        키가 없거나 실패하면 무료 공개 뉴스(Google News RSS) 기반 지연 신호로 폴백한다.
        둘 다 실패하면 빈 리스트(데이터 없음) — 난수 목업은 생성하지 않는다.
        """
        if not self.api_key:
            self.logger.warning("한국공항공사 API 키 없음 → 뉴스 기반 지연 신호 폴백 사용")
            return await self._collect_news_fallback()

        results = []
        search_date = datetime.now().strftime("%Y%m%d")

        for airport_code, airport_name in self.DOMESTIC_AIRPORTS.items():
            try:
                airport_data = {
                    "airport_code": airport_code,
                    "airport_name": airport_name,
                    "date": search_date,
                    "departures": [],
                    "arrivals": [],
                    "collected_at": datetime.now().isoformat(),
                }

                # 출발편 조회
                try:
                    dep_response = await self._fetch_departures(airport_code, search_date)
                    dep_items = self._extract_items(dep_response)
                    airport_data["departures"] = dep_items
                except Exception as e:
                    self.logger.warning(f"출발편 조회 실패 ({airport_code}): {e}")

                # 도착편 조회
                try:
                    arr_response = await self._fetch_arrivals(airport_code, search_date)
                    arr_items = self._extract_items(arr_response)
                    airport_data["arrivals"] = arr_items
                except Exception as e:
                    self.logger.warning(f"도착편 조회 실패 ({airport_code}): {e}")

                results.append(airport_data)

            except Exception as e:
                self.logger.error(f"공항 {airport_code} 데이터 수집 실패: {e}")
                continue

        # API 호출이 모두 실패한 경우 뉴스 기반 폴백
        if not results or all(
            not r["departures"] and not r["arrivals"] for r in results
        ):
            self.logger.warning("운항정보 API 수집 실패 → 뉴스 기반 지연 신호 폴백")
            return await self._collect_news_fallback()

        self.logger.info(f"운항정보 {len(results)}개 공항 수집 완료")
        return results

    def _extract_items(self, response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """API 응답에서 항목 추출"""
        try:
            body = response.get("response", {}).get("body", {})
            items = body.get("items", {})

            if not items:
                return []

            item_list = items.get("item", [])

            # 단일 항목인 경우 리스트로 변환
            if isinstance(item_list, dict):
                item_list = [item_list]

            return item_list
        except Exception as e:
            self.logger.error(f"응답 파싱 오류: {e}")
            return []

    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        수집된 데이터를 표준 형식으로 변환

        Args:
            raw_data: 수집된 공항 운항정보

        Returns:
            변환된 운영위험 데이터
        """
        # 이미 변환된 데이터인 경우 (목업 데이터 등)
        if raw_data.get("total_flights") is not None and raw_data.get("operational_score") is None:
            # 목업 데이터에서 operational_score 계산
            delay_rate = raw_data.get("delay_rate", 0)
            cancellation_rate = raw_data.get("cancellation_rate", 0)
            avg_delay = raw_data.get("average_delay_minutes", 0)
            total_flights = raw_data.get("total_flights", 0)

            congestion_level = self._calculate_congestion_level(total_flights)
            operational_score = self._calculate_operational_score(
                delay_rate, cancellation_rate, avg_delay, congestion_level
            )

            return {
                **raw_data,
                "congestion_level": congestion_level,
                "operational_score": round(operational_score, 2),
                "source": self.source_name,
            }

        departures = raw_data.get("departures", [])
        arrivals = raw_data.get("arrivals", [])
        all_flights = departures + arrivals

        total_flights = len(all_flights)
        if total_flights == 0:
            return {
                "airport_code": raw_data["airport_code"],
                "airport_name": raw_data["airport_name"],
                "date": raw_data["date"],
                "total_flights": 0,
                "delayed_flights": 0,
                "cancelled_flights": 0,
                "delay_rate": 0,
                "cancellation_rate": 0,
                "average_delay_minutes": 0,
                "congestion_level": "LOW",
                "operational_score": 10,
                "collected_at": raw_data["collected_at"],
                "source": self.source_name,
            }

        # 지연/결항 편수 계산
        delayed_flights = 0
        cancelled_flights = 0
        total_delay_minutes = 0

        for flight in all_flights:
            status = flight.get("remark", "") or flight.get("flightStatus", "")

            if "지연" in status or self._is_delayed(flight):
                delayed_flights += 1
                delay_mins = self._calculate_delay_minutes(flight)
                total_delay_minutes += delay_mins

            if "결항" in status or "취소" in status:
                cancelled_flights += 1

        # 지연율 및 결항율 계산
        delay_rate = (delayed_flights / total_flights) * 100 if total_flights > 0 else 0
        cancellation_rate = (cancelled_flights / total_flights) * 100 if total_flights > 0 else 0
        avg_delay = total_delay_minutes / delayed_flights if delayed_flights > 0 else 0

        # 혼잡도 계산 (시간당 평균 운항 편수 기준)
        congestion_level = self._calculate_congestion_level(total_flights)

        # 운영 위험 점수 계산
        operational_score = self._calculate_operational_score(
            delay_rate, cancellation_rate, avg_delay, congestion_level
        )

        return {
            "airport_code": raw_data["airport_code"],
            "airport_name": raw_data["airport_name"],
            "date": raw_data["date"],
            "total_flights": total_flights,
            "departure_count": len(departures),
            "arrival_count": len(arrivals),
            "delayed_flights": delayed_flights,
            "cancelled_flights": cancelled_flights,
            "delay_rate": round(delay_rate, 2),
            "cancellation_rate": round(cancellation_rate, 2),
            "average_delay_minutes": round(avg_delay, 1),
            "congestion_level": congestion_level,
            "operational_score": round(operational_score, 2),
            "collected_at": raw_data["collected_at"],
            "source": self.source_name,
        }

    def _is_delayed(self, flight: Dict[str, Any]) -> bool:
        """항공편 지연 여부 확인 (예정시각 vs 변경시각)"""
        scheduled = flight.get("scheduleTime", "") or flight.get("etd", "")
        actual = flight.get("estimatedTime", "") or flight.get("atd", "")

        if not scheduled or not actual:
            return False

        try:
            # 시간 형식: HHMM 또는 HH:MM
            scheduled_time = scheduled.replace(":", "")
            actual_time = actual.replace(":", "")

            sch_mins = int(scheduled_time[:2]) * 60 + int(scheduled_time[2:4])
            act_mins = int(actual_time[:2]) * 60 + int(actual_time[2:4])

            # 15분 이상 지연이면 지연으로 판정
            return (act_mins - sch_mins) >= 15
        except (ValueError, IndexError):
            return False

    def _calculate_delay_minutes(self, flight: Dict[str, Any]) -> int:
        """지연 시간(분) 계산"""
        scheduled = flight.get("scheduleTime", "") or flight.get("etd", "")
        actual = flight.get("estimatedTime", "") or flight.get("atd", "")

        if not scheduled or not actual:
            return 0

        try:
            scheduled_time = scheduled.replace(":", "")
            actual_time = actual.replace(":", "")

            sch_mins = int(scheduled_time[:2]) * 60 + int(scheduled_time[2:4])
            act_mins = int(actual_time[:2]) * 60 + int(actual_time[2:4])

            delay = act_mins - sch_mins
            return max(0, delay)
        except (ValueError, IndexError):
            return 0

    def _calculate_congestion_level(self, total_flights: int) -> str:
        """혼잡도 레벨 계산"""
        # 일일 운항 편수 기준
        if total_flights >= 200:
            return "CRITICAL"
        elif total_flights >= 100:
            return "HIGH"
        elif total_flights >= 50:
            return "MODERATE"
        else:
            return "LOW"

    def _calculate_operational_score(
        self,
        delay_rate: float,
        cancellation_rate: float,
        avg_delay: float,
        congestion_level: str
    ) -> float:
        """
        운영 위험 점수 계산 (0-100)

        Args:
            delay_rate: 지연율 (%)
            cancellation_rate: 결항율 (%)
            avg_delay: 평균 지연 시간 (분)
            congestion_level: 혼잡도

        Returns:
            운영 위험 점수
        """
        # 지연율 점수 (0-40점): 지연율 20% 이상이면 최대
        delay_score = min(40, delay_rate * 2)

        # 결항율 점수 (0-35점): 결항율 5% 이상이면 최대
        cancel_score = min(35, cancellation_rate * 7)

        # 평균 지연시간 점수 (0-15점): 60분 이상이면 최대
        delay_time_score = min(15, avg_delay / 4)

        # 혼잡도 점수 (0-10점)
        congestion_scores = {
            "LOW": 0,
            "MODERATE": 3,
            "HIGH": 7,
            "CRITICAL": 10,
        }
        congestion_score = congestion_scores.get(congestion_level, 0)

        total = delay_score + cancel_score + delay_time_score + congestion_score
        return min(100, max(0, total))

    def validate(self, data: Dict[str, Any]) -> bool:
        """데이터 유효성 검증"""
        # 공항 코드 필수
        if not data.get("airport_code"):
            return False

        # 점수 범위 확인
        score = data.get("operational_score", -1)
        if score < 0 or score > 100:
            return False

        # 비율 범위 확인
        delay_rate = data.get("delay_rate", -1)
        cancel_rate = data.get("cancellation_rate", -1)
        if delay_rate < 0 or delay_rate > 100:
            return False
        if cancel_rate < 0 or cancel_rate > 100:
            return False

        return True

    # 뉴스 기반 폴백 설정 (무료 공개 소스)
    NEWS_RSS = "https://news.google.com/rss/search"

    async def _collect_news_fallback(self) -> List[Dict[str, Any]]:
        """Google News RSS 기반 운항 지연 신호 폴백 (무료, 키 불필요)

        주의: 이 폴백의 delay_rate/cancellation_rate는 실측 통계가 아니라
        최근 7일 뉴스 신호량으로 추정한 '코스 프록시(coarse proxy)'다.
        실측 지연율은 한국공항공사(data.go.kr) 키가 있을 때만 산출된다.
        뉴스 신호가 전혀 없으면 해당 공항은 결과에서 제외(=데이터 없음)된다.
        """
        now = datetime.now()
        search_date = now.strftime("%Y%m%d")
        results: List[Dict[str, Any]] = []

        for airport_code, airport_name in self.DOMESTIC_AIRPORTS.items():
            try:
                delay_hits, cancel_hits = await self._news_disruption_signal(airport_name)
            except Exception as e:
                self.logger.warning("뉴스 신호 수집 실패 (%s): %s", airport_code, e)
                continue

            # 신호가 전혀 없으면 제외 (no-data) — 0으로 채워 위험을 왜곡하지 않음
            if delay_hits == 0 and cancel_hits == 0:
                continue

            delay_rate = self._signal_to_rate(delay_hits, buckets=((6, 25.0), (3, 16.0), (1, 8.0)))
            cancel_rate = self._signal_to_rate(cancel_hits, buckets=((3, 5.0), (1, 2.0)))

            results.append({
                "airport_code": airport_code,
                "airport_name": airport_name,
                "date": search_date,
                "departures": [],
                "arrivals": [],
                "total_flights": 0,  # 뉴스 폴백은 운항편수 미상
                "departure_count": 0,
                "arrival_count": 0,
                "delayed_flights": 0,
                "cancelled_flights": 0,
                "delay_rate": delay_rate,
                "cancellation_rate": cancel_rate,
                "average_delay_minutes": 0,
                "collected_at": now.isoformat(),
                "is_proxy": True,
                "proxy_source": "Google News RSS",
            })

        self.logger.info("뉴스 기반 지연 신호 폴백: %d개 공항", len(results))
        return results

    async def _news_disruption_signal(self, airport_name: str) -> tuple:
        """공항명으로 최근 7일 운항장애 뉴스 신호량 집계 (지연건수, 결항건수)"""
        query = f"{airport_name} (지연 OR 결항 OR 결항) when:7d"
        url = f"{self.NEWS_RSS}?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"

        response = await self.client.get(url, timeout=20.0)
        response.raise_for_status()
        root = ET.fromstring(response.text)

        delay_hits = 0
        cancel_hits = 0
        for item in root.iter("item"):
            title = (item.findtext("title") or "")
            if airport_name not in title:
                continue  # 제목에 공항명이 없으면 관련도 낮음 → 제외
            if "지연" in title:
                delay_hits += 1
            if "결항" in title or "취소" in title:
                cancel_hits += 1
        return delay_hits, cancel_hits

    @staticmethod
    def _signal_to_rate(hits: int, buckets) -> float:
        """뉴스 신호 건수를 코스 프록시 비율(%)로 변환"""
        for threshold, rate in buckets:
            if hits >= threshold:
                return rate
        return 0.0

    def get_summary(self, data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        수집된 데이터의 요약 통계

        Args:
            data_list: 변환된 데이터 리스트

        Returns:
            요약 통계
        """
        if not data_list:
            return {
                "total_airports": 0,
                "total_flights": 0,
                "average_delay_rate": 0,
                "average_cancellation_rate": 0,
                "high_risk_airports": [],
            }

        total_flights = sum(d.get("total_flights", 0) for d in data_list)
        delay_rates = [d.get("delay_rate", 0) for d in data_list]
        cancel_rates = [d.get("cancellation_rate", 0) for d in data_list]

        avg_delay_rate = sum(delay_rates) / len(delay_rates) if delay_rates else 0
        avg_cancel_rate = sum(cancel_rates) / len(cancel_rates) if cancel_rates else 0

        # 고위험 공항 (지연율 15% 이상 또는 결항율 5% 이상)
        high_risk = [
            {
                "airport_code": d["airport_code"],
                "airport_name": d["airport_name"],
                "delay_rate": d.get("delay_rate", 0),
                "cancellation_rate": d.get("cancellation_rate", 0),
                "operational_score": d.get("operational_score", 0),
            }
            for d in data_list
            if d.get("delay_rate", 0) >= 15 or d.get("cancellation_rate", 0) >= 5
        ]

        return {
            "total_airports": len(data_list),
            "total_flights": total_flights,
            "average_delay_rate": round(avg_delay_rate, 2),
            "average_cancellation_rate": round(avg_cancel_rate, 2),
            "high_risk_airports": sorted(
                high_risk,
                key=lambda x: x["operational_score"],
                reverse=True
            ),
        }
