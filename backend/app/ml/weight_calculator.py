"""
가중치 자동 산출 모듈

3가지 방법(상관분석, Ridge 회귀, Random Forest) + 앙상블로
카테고리 가중치를 데이터 기반으로 산출합니다.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# 기본 가중치 (risk_calculator.py와 동일)
DEFAULT_CATEGORY_WEIGHTS = {
    "weather": 0.20,
    "aviation": 0.25,
    "security": 0.20,
    "health": 0.15,
    "operational": 0.10,
    "external": 0.10,
}

CATEGORY_CODES = ["weather", "aviation", "security", "health", "operational", "external"]

# 가중치 허용 범위 (극단값 방지)
MIN_WEIGHT = 0.05
MAX_WEIGHT = 0.50


class WeightCalculator:
    """카테고리 가중치 자동 산출"""

    def __init__(self, min_samples: int = 30):
        self.min_samples = min_samples

    def correlation_weights(
        self, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, float]:
        """
        방법 1: |Pearson 상관계수| 비례 가중치.
        """
        correlations = {}
        for col in X.columns:
            valid = X[[col]].join(y).dropna()
            if len(valid) < self.min_samples:
                correlations[col] = 0.0
                continue

            x_vals = valid[col].values
            y_vals = valid.iloc[:, -1].values

            if np.std(x_vals) == 0 or np.std(y_vals) == 0:
                correlations[col] = 0.0
                continue

            r, _ = stats.pearsonr(x_vals, y_vals)
            correlations[col] = abs(float(r))

        return self._normalize_weights(correlations)

    def regression_weights(
        self, X: pd.DataFrame, y: pd.Series, alpha: float = 1.0
    ) -> Dict[str, float]:
        """
        방법 2: Ridge 회귀 표준화 계수 기반 가중치.
        """
        valid = X.join(y).replace([np.inf, -np.inf], np.nan).dropna()
        if len(valid) < self.min_samples:
            return self._equal_weights(X.columns)

        X_clean = valid[X.columns].values
        y_clean = valid.iloc[:, -1].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_clean)

        model = Ridge(alpha=alpha)
        model.fit(X_scaled, y_clean)

        abs_coefs = np.abs(model.coef_)
        total = abs_coefs.sum()
        if total == 0:
            return self._equal_weights(X.columns)

        weights = abs_coefs / total
        return dict(zip(X.columns, [float(w) for w in weights]))

    def random_forest_weights(
        self, X: pd.DataFrame, y: pd.Series, n_estimators: int = 100
    ) -> Dict[str, float]:
        """
        방법 3: Random Forest 변수 중요도 기반 가중치.
        """
        valid = X.join(y).replace([np.inf, -np.inf], np.nan).dropna()
        if len(valid) < self.min_samples:
            return self._equal_weights(X.columns)

        X_clean = valid[X.columns].values
        y_clean = valid.iloc[:, -1].values

        model = RandomForestRegressor(
            n_estimators=n_estimators,
            random_state=42,
            max_depth=5,
            min_samples_leaf=5,
        )
        model.fit(X_clean, y_clean)

        importances = model.feature_importances_
        return dict(zip(X.columns, [float(v) for v in importances]))

    def ensemble_weights(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        method_weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        """
        앙상블: 3가지 방법의 가중 평균.

        Returns:
            (final_weights, metadata)
        """
        if method_weights is None:
            method_weights = {"correlation": 0.3, "regression": 0.4, "rf": 0.3}

        corr_w = self.correlation_weights(X, y)
        reg_w = self.regression_weights(X, y)
        rf_w = self.random_forest_weights(X, y)

        final = {}
        for col in X.columns:
            final[col] = (
                corr_w.get(col, 0) * method_weights["correlation"]
                + reg_w.get(col, 0) * method_weights["regression"]
                + rf_w.get(col, 0) * method_weights["rf"]
            )

        final = self._normalize_weights(final)
        final = self._clamp_weights(final)

        metadata = {
            "method_weights": method_weights,
            "correlation_weights": corr_w,
            "regression_weights": reg_w,
            "rf_weights": rf_w,
        }

        return final, metadata

    def variance_based_weights(self, X: pd.DataFrame) -> Dict[str, float]:
        """
        폴백: 변동계수(CV) 기반 + 기본값 50:50 블렌딩.
        데이터가 부족할 때 사용.
        """
        cv_scores = {}
        for col in X.columns:
            series = X[col].dropna()
            if len(series) == 0 or series.mean() == 0:
                cv_scores[col] = 0.0
            else:
                cv_scores[col] = float(series.std() / series.mean())

        total_cv = sum(cv_scores.values())
        if total_cv == 0:
            return DEFAULT_CATEGORY_WEIGHTS.copy()

        data_weights = {k: v / total_cv for k, v in cv_scores.items()}

        blended = {}
        for k in X.columns:
            blended[k] = (
                data_weights.get(k, 0) * 0.5
                + DEFAULT_CATEGORY_WEIGHTS.get(k, 1 / 6) * 0.5
            )

        return self._normalize_weights(blended)

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """가중치 합이 1.0이 되도록 정규화"""
        total = sum(weights.values())
        if total == 0:
            n = len(weights)
            return {k: round(1.0 / n, 4) for k in weights}
        return {k: round(v / total, 4) for k, v in weights.items()}

    def _clamp_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """극단값 방지: MIN_WEIGHT~MAX_WEIGHT 범위로 클램핑 후 재정규화"""
        clamped = {k: max(MIN_WEIGHT, min(MAX_WEIGHT, v)) for k, v in weights.items()}
        return self._normalize_weights(clamped)

    def _equal_weights(self, columns) -> Dict[str, float]:
        n = len(columns)
        return {col: round(1.0 / n, 4) for col in columns}
