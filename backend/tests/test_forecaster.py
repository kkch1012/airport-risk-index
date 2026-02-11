"""
RiskForecaster 단위 테스트
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ml.forecaster import ForecastPoint, ForecastResult, RiskForecaster


def _make_series(values, start_date=None):
    """테스트용 pd.Series 생성 (date index)"""
    if start_date is None:
        start_date = date(2026, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(len(values))]
    return pd.Series(values, index=pd.DatetimeIndex(dates))


class TestHoltLinearForecasting:
    """이중지수평활법 테스트"""

    def test_forecast_returns_correct_horizon(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert len(result.predictions) == 7

    def test_forecast_14_days(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=14)
        assert result is not None
        assert len(result.predictions) == 14

    def test_forecast_values_in_range(self):
        series = _make_series(np.linspace(20, 60, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        for pt in result.predictions:
            assert 0 <= pt.value <= 100
            assert 0 <= pt.lower_ci <= 100
            assert 0 <= pt.upper_ci <= 100

    def test_confidence_intervals_widen(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        widths = [pt.upper_ci - pt.lower_ci for pt in result.predictions]
        for i in range(1, len(widths)):
            assert widths[i] >= widths[i - 1] - 0.1  # 허용오차

    def test_ci_bounds_ordering(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        for pt in result.predictions:
            assert pt.lower_ci <= pt.value <= pt.upper_ci

    def test_constant_series(self):
        series = _make_series([50.0] * 60)
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        for pt in result.predictions:
            assert abs(pt.value - 50.0) < 5.0

    def test_upward_trend(self):
        series = _make_series(np.linspace(20, 60, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=3)
        assert result is not None
        assert result.predictions[0].value > 60.0 - 5.0

    def test_downward_trend(self):
        series = _make_series(np.linspace(80, 40, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=3)
        assert result is not None
        assert result.predictions[0].value < 40.0 + 5.0

    def test_method_is_holt(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert result.method == "holt_linear"

    def test_metrics_present(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert "mae" in result.metrics
        assert "rmse" in result.metrics
        assert result.metrics["mae"] >= 0
        assert result.metrics["rmse"] >= 0

    def test_dates_are_consecutive(self):
        start = date(2026, 2, 1)
        series = _make_series(np.linspace(30, 50, 60), start_date=start)
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        last_date = start + timedelta(days=59)
        for i, pt in enumerate(result.predictions):
            assert pt.date == last_date + timedelta(days=i + 1)

    def test_last_observed(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert result.data_points_used == 60
        assert result.last_observed_value == round(50.0, 1)


class TestLinearFallback:
    """Ridge 회귀 폴백 테스트"""

    def test_fallback_on_short_data(self):
        series = _make_series(np.linspace(30, 50, 15))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert result.method == "linear_fallback"

    def test_fallback_produces_valid_result(self):
        series = _make_series(np.linspace(30, 50, 15))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert len(result.predictions) == 7
        for pt in result.predictions:
            assert 0 <= pt.value <= 100
            assert pt.lower_ci <= pt.value <= pt.upper_ci

    def test_fallback_with_10_points(self):
        series = _make_series(np.linspace(40, 50, 10))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert result.method == "linear_fallback"
        assert result.data_points_used == 10

    def test_fallback_metrics(self):
        series = _make_series(np.linspace(30, 50, 15))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert "mae" in result.metrics
        assert "rmse" in result.metrics


class TestForecastEdgeCases:
    """엣지 케이스 테스트"""

    def test_insufficient_data_returns_none(self):
        series = _make_series([50.0, 60.0])
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        # 3개 미만이면 None
        assert result is None

    def test_3_points_uses_fallback(self):
        series = _make_series([40.0, 45.0, 50.0])
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=3)
        assert result is not None
        assert result.method == "linear_fallback"

    def test_series_with_nans(self):
        values = list(np.linspace(30, 50, 60))
        values[10] = np.nan
        values[20] = np.nan
        values[30] = np.nan
        series = _make_series(values)
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        for pt in result.predictions:
            assert not np.isnan(pt.value)

    def test_all_zero_series(self):
        series = _make_series([0.0] * 60)
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        for pt in result.predictions:
            assert pt.value == 0.0

    def test_near_100_series(self):
        series = _make_series([95.0 + np.random.random() * 5 for _ in range(60)])
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        for pt in result.predictions:
            assert pt.value <= 100
            assert pt.upper_ci <= 100

    def test_horizon_clamped_to_max(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=30)
        assert result is not None
        assert len(result.predictions) == 14  # MAX_HORIZON

    def test_horizon_clamped_to_min(self):
        series = _make_series(np.linspace(30, 50, 60))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=0)
        assert result is not None
        assert len(result.predictions) == 1

    def test_noisy_series(self):
        np.random.seed(42)
        trend = np.linspace(30, 50, 60)
        noise = np.random.normal(0, 5, 60)
        series = _make_series(np.clip(trend + noise, 0, 100))
        forecaster = RiskForecaster()
        result = forecaster.forecast(series, horizon=7)
        assert result is not None
        assert result.method == "holt_linear"
        # 노이즈가 있으면 CI가 더 넓어야 함
        assert result.predictions[-1].upper_ci - result.predictions[-1].lower_ci > 0
