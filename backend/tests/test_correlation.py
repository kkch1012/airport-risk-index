"""
상관분석 모듈 테스트
"""

import numpy as np
import pandas as pd
import pytest

from app.ml.correlation import CorrelationAnalyzer


class TestFactorTargetCorrelations:
    """피처-타겟 상관분석 테스트"""

    def test_high_correlation_detected(self):
        """높은 상관관계가 올바르게 감지되는지"""
        np.random.seed(42)
        n = 100
        weather = np.random.uniform(10, 80, n)
        total_score = 0.8 * weather + np.random.normal(0, 5, n)

        X = pd.DataFrame({"weather": weather})
        y = pd.Series(total_score, name="total_score")

        analyzer = CorrelationAnalyzer(min_samples=30)
        results = analyzer.analyze_factor_target_correlations(X, y)

        assert "weather" in results
        assert results["weather"]["significant"] is True
        assert results["weather"]["pearson_r"] > 0.8

    def test_no_correlation(self):
        """무상관 데이터에서 유의하지 않음"""
        np.random.seed(42)
        n = 100
        X = pd.DataFrame({"random": np.random.uniform(0, 100, n)})
        y = pd.Series(np.random.uniform(0, 100, n), name="total_score")

        analyzer = CorrelationAnalyzer(min_samples=30)
        results = analyzer.analyze_factor_target_correlations(X, y)

        assert "random" in results
        assert abs(results["random"]["pearson_r"]) < 0.3

    def test_insufficient_data(self):
        """데이터 부족 시 insufficient_data 플래그"""
        X = pd.DataFrame({"weather": [10, 20, 30]})
        y = pd.Series([15, 25, 35], name="total_score")

        analyzer = CorrelationAnalyzer(min_samples=30)
        results = analyzer.analyze_factor_target_correlations(X, y)

        assert results["weather"]["insufficient_data"] is True
        assert results["weather"]["sample_size"] == 3

    def test_multiple_features(self):
        """다중 피처 동시 분석"""
        np.random.seed(42)
        n = 50
        X = pd.DataFrame({
            "weather": np.random.uniform(0, 100, n),
            "aviation": np.random.uniform(0, 100, n),
        })
        total = 0.6 * X["weather"] + 0.4 * X["aviation"] + np.random.normal(0, 3, n)
        y = pd.Series(total, name="total_score")

        analyzer = CorrelationAnalyzer(min_samples=30)
        results = analyzer.analyze_factor_target_correlations(X, y)

        assert "weather" in results
        assert "aviation" in results
        assert results["weather"]["sample_size"] == 50

    def test_zero_variance_feature(self):
        """분산 0인 피처 처리"""
        n = 50
        X = pd.DataFrame({"const": np.ones(n)})
        y = pd.Series(np.random.uniform(0, 100, n), name="total_score")

        analyzer = CorrelationAnalyzer(min_samples=30)
        results = analyzer.analyze_factor_target_correlations(X, y)

        assert results["const"]["pearson_r"] == 0.0
        assert results["const"]["significant"] is False


class TestCategoryCorrelations:
    """카테고리 간 상관분석 테스트"""

    def test_correlated_categories(self):
        """상관있는 카테고리 쌍 감지"""
        np.random.seed(42)
        n = 50
        weather = np.random.uniform(0, 100, n)
        operational = 0.7 * weather + np.random.normal(0, 10, n)
        aviation = np.random.uniform(0, 100, n)

        df = pd.DataFrame({
            "weather": weather,
            "operational": operational,
            "aviation": aviation,
        })

        analyzer = CorrelationAnalyzer(min_samples=30)
        results = analyzer.analyze_category_correlations(df)

        assert "weather" in results
        assert "operational" in results["weather"]
        assert results["weather"]["operational"]["pearson_r"] > 0.5


class TestCategoryVariance:
    """카테고리 분산 통계 테스트"""

    def test_variance_stats(self):
        """분산 통계가 올바르게 계산되는지"""
        np.random.seed(42)
        n = 50
        df = pd.DataFrame({
            "weather": np.random.uniform(10, 90, n),
            "aviation": np.ones(n) * 50,  # 분산 0
        })

        analyzer = CorrelationAnalyzer(min_samples=10)
        results = analyzer.analyze_category_variance(df)

        assert results["weather"]["std"] > 0
        assert results["weather"]["variance"] > 0
        assert results["aviation"]["std"] == 0.0

    def test_empty_dataframe(self):
        """빈 DataFrame 처리"""
        df = pd.DataFrame({"weather": pd.Series(dtype=float)})

        analyzer = CorrelationAnalyzer()
        results = analyzer.analyze_category_variance(df)

        assert results["weather"]["mean"] == 0
