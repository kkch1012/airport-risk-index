"""
가중치 자동 산출 테스트
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.weight_calculator import (
    DEFAULT_CATEGORY_WEIGHTS,
    WeightCalculator,
)


def _make_synthetic_data(n=100, seed=42):
    """테스트용 합성 데이터 생성"""
    np.random.seed(seed)
    weather = np.random.uniform(0, 100, n)
    aviation = np.random.uniform(0, 100, n)
    security = np.random.uniform(0, 100, n)
    health = np.random.uniform(0, 100, n)
    operational = np.random.uniform(0, 100, n)
    external = np.random.uniform(0, 100, n)

    # total_score: weather와 aviation에 더 높은 비중
    total = (
        0.35 * weather + 0.30 * aviation + 0.15 * security
        + 0.10 * health + 0.05 * operational + 0.05 * external
        + np.random.normal(0, 3, n)
    )

    X = pd.DataFrame({
        "weather": weather,
        "aviation": aviation,
        "security": security,
        "health": health,
        "operational": operational,
        "external": external,
    })
    y = pd.Series(total, name="total_score")
    return X, y


class TestCorrelationWeights:
    """상관분석 기반 가중치 테스트"""

    def test_weights_sum_to_one(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights = calc.correlation_weights(X, y)
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_higher_corr_gets_higher_weight(self):
        """높은 상관관계 카테고리가 더 높은 가중치"""
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights = calc.correlation_weights(X, y)
        # weather(0.35)와 aviation(0.30)이 가장 큰 가중치를 받아야 함
        assert weights["weather"] > weights["external"]

    def test_insufficient_data_equal_weights(self):
        """데이터 부족 시 균등 가중치"""
        X = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        y = pd.Series([5, 6], name="total_score")
        calc = WeightCalculator(min_samples=30)
        weights = calc.correlation_weights(X, y)
        assert abs(weights["a"] - weights["b"]) < 0.01


class TestRegressionWeights:
    """Ridge 회귀 기반 가중치 테스트"""

    def test_weights_sum_to_one(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights = calc.regression_weights(X, y)
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_dominant_feature_gets_higher_weight(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights = calc.regression_weights(X, y)
        assert weights["weather"] > weights["external"]

    def test_insufficient_data(self):
        X = pd.DataFrame({"a": [1], "b": [2]})
        y = pd.Series([3], name="total_score")
        calc = WeightCalculator(min_samples=30)
        weights = calc.regression_weights(X, y)
        assert abs(weights["a"] - weights["b"]) < 0.01


class TestRandomForestWeights:
    """Random Forest 기반 가중치 테스트"""

    def test_weights_sum_to_one(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights = calc.random_forest_weights(X, y)
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_important_features_detected(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights = calc.random_forest_weights(X, y)
        # weather + aviation 합이 전체의 상당 비중 차지
        top_two = weights["weather"] + weights["aviation"]
        assert top_two > 0.3


class TestEnsembleWeights:
    """앙상블 가중치 테스트"""

    def test_weights_sum_to_one(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights, metadata = calc.ensemble_weights(X, y)
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_metadata_contains_all_methods(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        _, metadata = calc.ensemble_weights(X, y)
        assert "correlation_weights" in metadata
        assert "regression_weights" in metadata
        assert "rf_weights" in metadata

    def test_weights_within_bounds(self):
        """극단값 클램핑: 0.05 ~ 0.50"""
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        weights, _ = calc.ensemble_weights(X, y)
        for w in weights.values():
            assert 0.04 <= w <= 0.51  # 정규화 반올림 허용

    def test_custom_method_weights(self):
        X, y = _make_synthetic_data()
        calc = WeightCalculator(min_samples=30)
        # 상관분석만 100% 사용
        weights, _ = calc.ensemble_weights(
            X, y, method_weights={"correlation": 1.0, "regression": 0.0, "rf": 0.0}
        )
        assert abs(sum(weights.values()) - 1.0) < 0.01


class TestVarianceBasedWeights:
    """분산 기반 폴백 가중치 테스트"""

    def test_weights_sum_to_one(self):
        X, _ = _make_synthetic_data()
        calc = WeightCalculator()
        weights = calc.variance_based_weights(X)
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_blends_with_defaults(self):
        """기본값과 50:50 블렌딩 — 기본값 근처 유지"""
        X, _ = _make_synthetic_data()
        calc = WeightCalculator()
        weights = calc.variance_based_weights(X)
        # 균일분포이므로 분산 비슷 → 기본값에 가까워야 함
        for cat, default_w in DEFAULT_CATEGORY_WEIGHTS.items():
            if cat in weights:
                assert abs(weights[cat] - default_w) < 0.15

    def test_zero_variance_uses_defaults(self):
        """모든 분산 0이면 기본값 반환"""
        n = 50
        X = pd.DataFrame({
            "weather": np.zeros(n),
            "aviation": np.zeros(n),
        })
        calc = WeightCalculator()
        weights = calc.variance_based_weights(X)
        assert weights == DEFAULT_CATEGORY_WEIGHTS
