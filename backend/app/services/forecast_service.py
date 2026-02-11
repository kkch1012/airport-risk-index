"""
예측 서비스

데이터 로드 → 시계열 추출 → 예측 실행 오케스트레이션.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.data_loader import CATEGORY_CODES, AnalysisDataLoader
from app.ml.forecaster import RiskForecaster

logger = logging.getLogger(__name__)


class ForecastService:
    """예측 라이프사이클 관리"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.data_loader = AnalysisDataLoader(session)
        self.forecaster = RiskForecaster()

    async def forecast_airport(
        self,
        airport_code: str,
        horizon: int = 7,
        category: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        단일 공항 예측.

        Args:
            airport_code: IATA 공항 코드
            horizon: 예측 일수
            category: None이면 total_score, 아니면 특정 카테고리

        Returns:
            AirportForecastResponse 형태 dict, 데이터 부족 시 None
        """
        # 유효하지 않은 카테고리는 total로 폴백
        valid_category = category if category and category in CATEGORY_CODES else None

        series = await self._get_series(airport_code, valid_category)
        if series is None or len(series) < 3:
            return None

        result = self.forecaster.forecast(series, horizon=horizon)
        if result is None:
            return None

        cat_label = valid_category or "total"

        return {
            "airport_code": airport_code,
            "category": cat_label,
            "horizon": horizon,
            "last_observed": {
                "date": str(result.last_observed_date),
                "value": result.last_observed_value,
                "lower_ci": result.last_observed_value,
                "upper_ci": result.last_observed_value,
            },
            "predictions": [
                {
                    "date": str(pt.date),
                    "value": pt.value,
                    "lower_ci": pt.lower_ci,
                    "upper_ci": pt.upper_ci,
                }
                for pt in result.predictions
            ],
            "metrics": {
                "mae": result.metrics.get("mae", 0),
                "rmse": result.metrics.get("rmse", 0),
                "method": result.method,
                "data_points_used": result.data_points_used,
            },
        }

    async def forecast_all_airports(
        self, horizon: int = 7
    ) -> List[Dict[str, Any]]:
        """전체 공항 배치 예측 (Celery 태스크용)"""
        df = await self.data_loader.load_category_scores()
        if df.empty:
            return []

        airport_codes = df["airport_code"].unique().tolist()
        results = []

        for code in airport_codes:
            result = await self.forecast_airport(code, horizon=horizon)
            if result:
                results.append(result)

        logger.info("Batch forecast: %d/%d airports", len(results), len(airport_codes))
        return results

    async def _get_series(
        self,
        airport_code: str,
        category: Optional[str] = None,
    ) -> Optional[pd.Series]:
        """DB에서 공항별 시계열 추출"""
        df = await self.data_loader.load_category_scores(
            airport_codes=[airport_code]
        )

        if df.empty:
            return None

        col = category if category and category in CATEGORY_CODES else "total_score"

        if col not in df.columns:
            return None

        # assessed_date를 index로, col 값을 Series로
        ts = df.set_index("assessed_date")[col].sort_index()
        # 같은 날짜 중복 시 평균
        ts = ts.groupby(ts.index).mean()
        ts.index = pd.DatetimeIndex(ts.index)

        return ts
