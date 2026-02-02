"""
데이터 수집기 기본 클래스
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import httpx
import logging

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """데이터 수집기 추상 기본 클래스"""

    name: str = "base"
    source_name: str = "Unknown"
    source_url: str = ""
    collection_interval: int = 3600  # 초 단위 (기본 1시간)

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.last_collected: Optional[datetime] = None
        self.logger = logging.getLogger(f"collector.{self.name}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        """HTTP 클라이언트 종료"""
        await self.client.aclose()

    @abstractmethod
    async def collect(self) -> List[Dict[str, Any]]:
        """
        데이터 수집 (구현 필수)

        Returns:
            수집된 원시 데이터 리스트
        """
        pass

    @abstractmethod
    def transform(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        데이터 변환 (구현 필수)

        Args:
            raw_data: 원시 데이터

        Returns:
            변환된 데이터
        """
        pass

    def validate(self, data: Dict[str, Any]) -> bool:
        """
        데이터 유효성 검증

        Args:
            data: 검증할 데이터

        Returns:
            유효 여부
        """
        return True

    async def run(self) -> Dict[str, Any]:
        """
        수집 실행

        Returns:
            수집 결과 요약
        """
        start_time = datetime.now()
        self.logger.info(f"[{self.name}] 데이터 수집 시작")

        try:
            # 1. 데이터 수집
            raw_data_list = await self.collect()
            self.logger.info(f"[{self.name}] {len(raw_data_list)}건 수집 완료")

            # 2. 데이터 변환
            transformed = []
            for raw_data in raw_data_list:
                try:
                    data = self.transform(raw_data)
                    if self.validate(data):
                        transformed.append(data)
                except Exception as e:
                    self.logger.warning(f"[{self.name}] 변환 실패: {e}")
                    continue

            # 3. 완료
            self.last_collected = datetime.now()
            elapsed = (self.last_collected - start_time).total_seconds()

            result = {
                "status": "success",
                "collector": self.name,
                "collected_count": len(raw_data_list),
                "transformed_count": len(transformed),
                "elapsed_seconds": round(elapsed, 2),
                "collected_at": self.last_collected.isoformat(),
                "data": transformed,
            }

            self.logger.info(
                f"[{self.name}] 수집 완료: {len(transformed)}건 ({elapsed:.2f}초)"
            )
            return result

        except Exception as e:
            self.logger.error(f"[{self.name}] 수집 실패: {e}")
            return {
                "status": "error",
                "collector": self.name,
                "error": str(e),
                "collected_at": datetime.now().isoformat(),
            }
