"""
ForecastService 통합 테스트
"""

from datetime import date, timedelta

import numpy as np
import pytest
import pytest_asyncio

from app.models.risk_history import CategoryScoreRecord, RiskAssessment
from app.services.forecast_service import ForecastService


CATEGORY_NAMES = {
    "weather": "기상",
    "aviation": "항공안전",
    "security": "보안",
    "health": "보건",
    "operational": "운영",
    "external": "외부요인",
}


def _risk_level(score: float) -> str:
    if score < 25:
        return "LOW"
    elif score < 50:
        return "MODERATE"
    elif score < 75:
        return "HIGH"
    return "CRITICAL"


async def _insert_synthetic_history(session, airport_code: str, days: int, base_score: float = 40.0):
    """합성 위험 이력 데이터 삽입 (선형 트렌드 + 노이즈)"""
    np.random.seed(42)
    start_date = date.today() - timedelta(days=days)

    for i in range(days):
        d = start_date + timedelta(days=i)
        score = base_score + (i * 0.3) + np.random.normal(0, 2)
        score = float(np.clip(score, 0, 100))

        assessment = RiskAssessment(
            airport_code=airport_code,
            airport_name=f"Test Airport {airport_code}",
            assessed_date=d,
            total_score=round(score, 1),
            risk_level=_risk_level(score),
        )
        session.add(assessment)
        await session.flush()

        for cat_code, cat_name in CATEGORY_NAMES.items():
            cat_score = float(np.clip(score + np.random.normal(0, 5), 0, 100))
            record = CategoryScoreRecord(
                assessment_id=assessment.id,
                category_code=cat_code,
                category_name=cat_name,
                score=round(cat_score, 1),
                level=_risk_level(cat_score),
                factors={},
            )
            session.add(record)

    await session.commit()


class TestForecastService:
    """ForecastService 통합 테스트"""

    @pytest.mark.asyncio
    async def test_forecast_with_sufficient_data(self, db_session):
        await _insert_synthetic_history(db_session, "ICN", days=60)
        service = ForecastService(db_session)
        result = await service.forecast_airport("ICN", horizon=7)

        assert result is not None
        assert result["airport_code"] == "ICN"
        assert result["category"] == "total"
        assert len(result["predictions"]) == 7
        assert result["metrics"]["method"] == "holt_linear"
        assert result["metrics"]["data_points_used"] == 60

    @pytest.mark.asyncio
    async def test_forecast_insufficient_data(self, db_session):
        await _insert_synthetic_history(db_session, "GMP", days=5)
        service = ForecastService(db_session)
        result = await service.forecast_airport("GMP", horizon=7)

        # 5일 데이터 → 폴백
        assert result is not None
        assert result["metrics"]["method"] == "linear_fallback"

    @pytest.mark.asyncio
    async def test_forecast_no_data(self, db_session):
        service = ForecastService(db_session)
        result = await service.forecast_airport("ZZZ", horizon=7)
        assert result is None

    @pytest.mark.asyncio
    async def test_forecast_per_category(self, db_session):
        await _insert_synthetic_history(db_session, "PUS", days=60)
        service = ForecastService(db_session)
        result = await service.forecast_airport("PUS", horizon=7, category="weather")

        assert result is not None
        assert result["category"] == "weather"
        assert len(result["predictions"]) == 7

    @pytest.mark.asyncio
    async def test_forecast_invalid_category_falls_to_total(self, db_session):
        await _insert_synthetic_history(db_session, "CJU", days=60)
        service = ForecastService(db_session)
        result = await service.forecast_airport("CJU", horizon=7, category="nonexistent")

        assert result is not None
        assert result["category"] == "total"

    @pytest.mark.asyncio
    async def test_forecast_predictions_structure(self, db_session):
        await _insert_synthetic_history(db_session, "TAE", days=60)
        service = ForecastService(db_session)
        result = await service.forecast_airport("TAE", horizon=7)

        assert result is not None
        for pt in result["predictions"]:
            assert "date" in pt
            assert "value" in pt
            assert "lower_ci" in pt
            assert "upper_ci" in pt
            assert 0 <= pt["value"] <= 100
            assert pt["lower_ci"] <= pt["value"] <= pt["upper_ci"]

    @pytest.mark.asyncio
    async def test_forecast_last_observed(self, db_session):
        await _insert_synthetic_history(db_session, "CJJ", days=60)
        service = ForecastService(db_session)
        result = await service.forecast_airport("CJJ", horizon=7)

        assert result is not None
        assert result["last_observed"] is not None
        assert "date" in result["last_observed"]
        assert "value" in result["last_observed"]

    @pytest.mark.asyncio
    async def test_forecast_all_airports(self, db_session):
        await _insert_synthetic_history(db_session, "ICN", days=60)
        await _insert_synthetic_history(db_session, "GMP", days=60, base_score=30.0)
        service = ForecastService(db_session)
        results = await service.forecast_all_airports(horizon=7)

        assert len(results) == 2
        codes = {r["airport_code"] for r in results}
        assert codes == {"ICN", "GMP"}
