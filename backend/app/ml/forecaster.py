"""
시계열 예측 모듈

Holt's Linear Exponential Smoothing (이중지수평활법) + Ridge 회귀 폴백으로
공항 위험지수 미래 예측 및 95% 신뢰구간을 산출합니다.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.linear_model import Ridge

logger = logging.getLogger(__name__)

MIN_DATA_POINTS = 30
MAX_HORIZON = 14
Z_95 = 1.96  # 95% 신뢰구간 z-value


@dataclass
class ForecastPoint:
    """단일 예측 포인트"""
    date: date
    value: float
    lower_ci: float
    upper_ci: float


@dataclass
class ForecastResult:
    """예측 결과"""
    predictions: List[ForecastPoint]
    method: str
    metrics: Dict[str, float] = field(default_factory=dict)
    data_points_used: int = 0
    last_observed_date: Optional[date] = None
    last_observed_value: float = 0.0


class RiskForecaster:
    """공항 위험지수 시계열 예측"""

    def __init__(self, min_data_points: int = MIN_DATA_POINTS):
        self.min_data_points = min_data_points

    def forecast(
        self,
        series: pd.Series,
        horizon: int = 7,
    ) -> Optional[ForecastResult]:
        """
        시계열 예측 실행.

        Args:
            series: DatetimeIndex(또는 date index), 값은 0-100 점수
            horizon: 예측 일수 (1-14)

        Returns:
            ForecastResult 또는 데이터 부족 시 None
        """
        horizon = max(1, min(horizon, MAX_HORIZON))

        # NaN 보간 + 정렬
        series = series.sort_index().interpolate(method="linear").dropna()

        if len(series) < 3:
            return None

        if len(series) >= self.min_data_points:
            try:
                return self._holt_linear(series, horizon)
            except Exception as e:
                logger.warning("Holt 평활 실패, Ridge 폴백: %s", e)

        return self._linear_fallback(series, horizon)

    def _holt_linear(
        self,
        series: pd.Series,
        horizon: int,
        alpha: Optional[float] = None,
        beta: Optional[float] = None,
    ) -> ForecastResult:
        """
        Holt's Linear (이중지수평활법).

        alpha, beta를 지정하지 않으면 scipy.optimize로 최적화.
        """
        values = series.values.astype(float)
        n = len(values)

        # 파라미터 최적화
        if alpha is None or beta is None:
            alpha, beta = self._optimize_holt_params(values)

        # 평활 실행
        level = np.zeros(n)
        trend = np.zeros(n)
        level[0] = values[0]
        trend[0] = values[1] - values[0] if n > 1 else 0.0

        for t in range(1, n):
            level[t] = alpha * values[t] + (1 - alpha) * (level[t - 1] + trend[t - 1])
            trend[t] = beta * (level[t] - level[t - 1]) + (1 - beta) * trend[t - 1]

        # 인샘플 잔차로 메트릭 계산
        fitted = np.zeros(n)
        fitted[0] = values[0]
        for t in range(1, n):
            fitted[t] = level[t - 1] + trend[t - 1]

        residuals = values[1:] - fitted[1:]
        residual_std = float(np.std(residuals)) if len(residuals) > 0 else 1.0
        mae = float(np.mean(np.abs(residuals))) if len(residuals) > 0 else 0.0
        rmse = float(np.sqrt(np.mean(residuals ** 2))) if len(residuals) > 0 else 0.0

        # 미래 예측
        last_level = level[-1]
        last_trend = trend[-1]
        last_date = series.index[-1]
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.date()

        predictions = []
        for h in range(1, horizon + 1):
            pred_value = last_level + h * last_trend
            pred_value = float(np.clip(pred_value, 0, 100))

            ci_width = Z_95 * residual_std * math.sqrt(h)
            lower = float(np.clip(pred_value - ci_width, 0, 100))
            upper = float(np.clip(pred_value + ci_width, 0, 100))

            pred_date = last_date + timedelta(days=h)
            predictions.append(ForecastPoint(
                date=pred_date,
                value=round(pred_value, 1),
                lower_ci=round(lower, 1),
                upper_ci=round(upper, 1),
            ))

        return ForecastResult(
            predictions=predictions,
            method="holt_linear",
            metrics={"mae": round(mae, 2), "rmse": round(rmse, 2), "alpha": round(alpha, 4), "beta": round(beta, 4)},
            data_points_used=n,
            last_observed_date=last_date,
            last_observed_value=round(float(values[-1]), 1),
        )

    def _optimize_holt_params(self, values: np.ndarray) -> Tuple[float, float]:
        """alpha, beta를 MSE 최소화로 최적화"""
        def mse_loss(params):
            a, b = params
            n = len(values)
            level = np.zeros(n)
            trend = np.zeros(n)
            level[0] = values[0]
            trend[0] = values[1] - values[0] if n > 1 else 0.0

            sse = 0.0
            for t in range(1, n):
                forecast_t = level[t - 1] + trend[t - 1]
                sse += (values[t] - forecast_t) ** 2
                level[t] = a * values[t] + (1 - a) * (level[t - 1] + trend[t - 1])
                trend[t] = b * (level[t] - level[t - 1]) + (1 - b) * trend[t - 1]

            return sse / (n - 1)

        result = minimize(
            mse_loss,
            x0=[0.3, 0.1],
            bounds=[(0.01, 0.99), (0.01, 0.99)],
            method="L-BFGS-B",
        )

        if result.success:
            return float(result.x[0]), float(result.x[1])
        return 0.3, 0.1

    def _linear_fallback(
        self,
        series: pd.Series,
        horizon: int,
    ) -> ForecastResult:
        """Ridge 회귀 폴백 (데이터 부족 시)"""
        values = series.values.astype(float)
        n = len(values)

        X = np.arange(n).reshape(-1, 1)
        model = Ridge(alpha=1.0)
        model.fit(X, values)

        fitted = model.predict(X)
        residuals = values - fitted
        residual_std = float(np.std(residuals)) if len(residuals) > 1 else 1.0
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals ** 2)))

        last_date = series.index[-1]
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.date()

        predictions = []
        for h in range(1, horizon + 1):
            pred_value = float(model.predict(np.array([[n - 1 + h]]))[0])
            pred_value = float(np.clip(pred_value, 0, 100))

            ci_width = Z_95 * residual_std * math.sqrt(h)
            lower = float(np.clip(pred_value - ci_width, 0, 100))
            upper = float(np.clip(pred_value + ci_width, 0, 100))

            pred_date = last_date + timedelta(days=h)
            predictions.append(ForecastPoint(
                date=pred_date,
                value=round(pred_value, 1),
                lower_ci=round(lower, 1),
                upper_ci=round(upper, 1),
            ))

        return ForecastResult(
            predictions=predictions,
            method="linear_fallback",
            metrics={"mae": round(mae, 2), "rmse": round(rmse, 2)},
            data_points_used=n,
            last_observed_date=last_date,
            last_observed_value=round(float(values[-1]), 1),
        )
