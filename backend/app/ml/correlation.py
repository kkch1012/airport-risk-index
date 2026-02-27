"""
상관분석 모듈

Pearson/Spearman 상관계수를 통해 카테고리 점수와
위험지수 간의 통계적 관계를 분석합니다.
"""

import logging
from typing import Any, Dict

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class CorrelationAnalyzer:
    """카테고리 점수 상관분석"""

    def __init__(self, min_samples: int = 30):
        self.min_samples = min_samples

    def analyze_factor_target_correlations(
        self,
        features_df: pd.DataFrame,
        target: pd.Series,
    ) -> Dict[str, Dict[str, Any]]:
        """
        각 피처(카테고리 점수)와 타겟(total_score) 간 상관분석.

        Returns:
            {
                "weather": {
                    "pearson_r": 0.42, "pearson_p": 0.001,
                    "spearman_r": 0.38, "spearman_p": 0.002,
                    "significant": True, "sample_size": 150
                }, ...
            }
        """
        results = {}
        for col in features_df.columns:
            valid = features_df[[col]].join(target).dropna()
            n = len(valid)

            if n < self.min_samples:
                results[col] = {"insufficient_data": True, "sample_size": n}
                continue

            x = valid[col].values
            y = valid.iloc[:, -1].values

            # 분산이 0이면 상관계수 계산 불가
            if np.std(x) < 1e-10 or np.std(y) < 1e-10:
                results[col] = {
                    "pearson_r": 0.0, "pearson_p": 1.0,
                    "spearman_r": 0.0, "spearman_p": 1.0,
                    "significant": False, "sample_size": n,
                }
                continue

            pearson_r, pearson_p = stats.pearsonr(x, y)
            spearman_r, spearman_p = stats.spearmanr(x, y)

            results[col] = {
                "pearson_r": round(float(pearson_r), 4),
                "pearson_p": round(float(pearson_p), 6),
                "spearman_r": round(float(spearman_r), 4),
                "spearman_p": round(float(spearman_p), 6),
                "significant": float(pearson_p) < 0.05,
                "sample_size": n,
            }

        return results

    def analyze_category_correlations(
        self, df: pd.DataFrame
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        카테고리 간 Pearson 상관 행렬.

        Returns:
            {"weather": {"aviation": {"pearson_r": 0.32, "pearson_p": 0.01}, ...}, ...}
        """
        cols = [c for c in df.columns if c in (
            "weather", "aviation", "security", "health", "operational", "external"
        )]
        results = {}

        for i, col_a in enumerate(cols):
            results[col_a] = {}
            for col_b in cols[i + 1:]:
                valid = df[[col_a, col_b]].dropna()
                if len(valid) < self.min_samples:
                    results[col_a][col_b] = {"insufficient_data": True}
                    continue

                x, y = valid[col_a].values, valid[col_b].values
                if np.std(x) < 1e-10 or np.std(y) < 1e-10:
                    results[col_a][col_b] = {"pearson_r": 0.0, "pearson_p": 1.0}
                    continue

                r, p = stats.pearsonr(x, y)
                results[col_a][col_b] = {
                    "pearson_r": round(float(r), 4),
                    "pearson_p": round(float(p), 6),
                }

        return results

    def analyze_category_variance(
        self, df: pd.DataFrame
    ) -> Dict[str, Dict[str, float]]:
        """
        카테고리별 분산 통계. 분산이 높은 카테고리가 더 정보량이 많음.

        Returns:
            {"weather": {"mean": 25.3, "std": 12.1, "variance": 146.4, "cv": 0.48}, ...}
        """
        cols = [c for c in df.columns if c in (
            "weather", "aviation", "security", "health", "operational", "external"
        )]
        results = {}

        for col in cols:
            series = df[col].dropna()
            if len(series) == 0:
                results[col] = {"mean": 0, "std": 0, "variance": 0, "cv": 0}
                continue

            mean = float(series.mean())
            std = float(series.std())
            results[col] = {
                "mean": round(mean, 2),
                "std": round(std, 2),
                "variance": round(std ** 2, 2),
                "cv": round(std / abs(mean), 4) if abs(mean) > 1e-10 else 0,
            }

        return results
