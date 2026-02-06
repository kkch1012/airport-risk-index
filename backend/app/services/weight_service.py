"""
가중치 관리 서비스

데이터 로드 → 상관분석 → 가중치 산출 → DB 저장/활성화 오케스트레이션.
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.correlation import CorrelationAnalyzer
from app.ml.data_loader import CATEGORY_CODES, AnalysisDataLoader
from app.ml.weight_calculator import DEFAULT_CATEGORY_WEIGHTS, WeightCalculator
from app.models.weight_history import WeightHistory

logger = logging.getLogger(__name__)


class WeightService:
    """가중치 라이프사이클 관리"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.data_loader = AnalysisDataLoader(session)

    async def get_active_weights(self) -> Optional[WeightHistory]:
        """현재 활성 가중치 조회"""
        stmt = (
            select(WeightHistory)
            .where(WeightHistory.is_active == True)  # noqa: E712
            .order_by(WeightHistory.calculated_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_category_weights(self) -> Dict[str, float]:
        """활성 가중치 dict 반환, 없으면 기본값"""
        active = await self.get_active_weights()
        if active and active.category_weights:
            return active.category_weights
        return DEFAULT_CATEGORY_WEIGHTS.copy()

    async def calculate_and_save_weights(
        self,
        method: str = "ensemble",
        lookback_days: int = 365,
    ) -> Optional[WeightHistory]:
        """
        전체 가중치 재산출 파이프라인.

        1. 데이터 충분성 확인
        2. 이력 데이터 로드
        3. 가중치 계산
        4. 기존 활성 가중치 비활성화
        5. 새 가중치 저장 + 활성화

        Returns: WeightHistory or None (데이터 부족 시)
        """
        if not await self.data_loader.has_sufficient_data():
            logger.warning(
                "Insufficient data for weight calculation (need >= %d)",
                self.data_loader.MIN_DATA_POINTS,
            )
            return None

        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        category_df = await self.data_loader.load_category_scores(
            start_date=start_date, end_date=end_date
        )

        if len(category_df) < self.data_loader.MIN_DATA_POINTS:
            logger.warning("Only %d data points available, skipping", len(category_df))
            return None

        feature_cols = [c for c in CATEGORY_CODES if c in category_df.columns]
        X = category_df[feature_cols]
        y = category_df["total_score"]
        y.name = "total_score"

        calculator = WeightCalculator(min_samples=self.data_loader.MIN_DATA_POINTS)

        try:
            if method == "ensemble":
                weights, metadata = calculator.ensemble_weights(X, y)
            elif method == "correlation":
                weights = calculator.correlation_weights(X, y)
                metadata = {"method": "correlation"}
            elif method == "regression":
                weights = calculator.regression_weights(X, y)
                metadata = {"method": "regression"}
            elif method == "rf":
                weights = calculator.random_forest_weights(X, y)
                metadata = {"method": "rf"}
            elif method == "variance":
                weights = calculator.variance_based_weights(X)
                metadata = {"method": "variance"}
            else:
                raise ValueError(f"Unknown method: {method}")
        except Exception:
            logger.exception("Weight calculation failed, using defaults")
            return None

        # 누락 카테고리 보완 + 재정규화
        for cat in CATEGORY_CODES:
            if cat not in weights:
                weights[cat] = DEFAULT_CATEGORY_WEIGHTS.get(cat, 1 / 6)
        total = sum(weights.values())
        weights = {k: round(v / total, 4) for k, v in weights.items()}

        # 기존 활성 가중치 비활성화
        await self._deactivate_all()

        history = WeightHistory(
            method=method,
            category_weights=weights,
            metadata_info=metadata,
            sample_size=len(category_df),
            analysis_period_start=start_date,
            analysis_period_end=end_date,
            is_active=True,
        )
        self.session.add(history)
        await self.session.commit()

        logger.info(
            "New weights activated: %s (method=%s, n=%d)",
            weights, method, len(category_df),
        )
        return history

    async def get_weight_history(self, limit: int = 10) -> List[WeightHistory]:
        """최근 가중치 산출 이력"""
        stmt = (
            select(WeightHistory)
            .order_by(WeightHistory.calculated_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def run_correlation_analysis(self) -> Dict[str, Any]:
        """
        상관분석 실행 (가중치 저장 없이).
        analytics API 엔드포인트용.
        """
        if not await self.data_loader.has_sufficient_data():
            return {"error": "insufficient_data", "min_required": self.data_loader.MIN_DATA_POINTS}

        category_df = await self.data_loader.load_category_scores()

        if len(category_df) == 0:
            return {"error": "no_data"}

        feature_cols = [c for c in CATEGORY_CODES if c in category_df.columns]
        X = category_df[feature_cols]

        target = category_df["total_score"]
        target.name = "total_score"

        analyzer = CorrelationAnalyzer(min_samples=self.data_loader.MIN_DATA_POINTS)

        factor_corrs = analyzer.analyze_factor_target_correlations(X, target)
        cross_corrs = analyzer.analyze_category_correlations(X)
        variance = analyzer.analyze_category_variance(X)

        return {
            "factor_correlations": factor_corrs,
            "cross_category_correlations": cross_corrs,
            "variance_analysis": variance,
            "sample_size": len(category_df),
            "analysis_period": {
                "start": str(category_df["assessed_date"].min()) if len(category_df) > 0 else "",
                "end": str(category_df["assessed_date"].max()) if len(category_df) > 0 else "",
            },
        }

    async def _deactivate_all(self):
        """전체 활성 가중치 비활성화"""
        stmt = (
            update(WeightHistory)
            .where(WeightHistory.is_active == True)  # noqa: E712
            .values(is_active=False)
        )
        await self.session.execute(stmt)
