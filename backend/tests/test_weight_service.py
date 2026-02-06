"""
가중치 관리 서비스 통합 테스트
"""

import random
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.ml.weight_calculator import DEFAULT_CATEGORY_WEIGHTS
from app.models.risk_history import CategoryScoreRecord, RiskAssessment
from app.services.weight_service import WeightService


@pytest_asyncio.fixture
async def db_session():
    """인메모리 SQLite 비동기 세션"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    import app.models.risk_history  # noqa: F401
    import app.models.weight_history  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_risk_data(session: AsyncSession, n_days: int = 50, n_airports: int = 5):
    """테스트용 위험지수 이력 데이터 삽입"""
    airports = ["ICN", "GMP", "PUS", "CJU", "TAE"][:n_airports]
    categories = ["weather", "aviation", "security", "health", "operational", "external"]
    cat_names = {"weather": "기상", "aviation": "항공안전", "security": "보안",
                 "health": "보건", "operational": "운영", "external": "외부"}

    random.seed(42)
    base_date = date.today() - timedelta(days=n_days)

    for day_offset in range(n_days):
        assessed = base_date + timedelta(days=day_offset)
        for code in airports:
            scores = {}
            for cat in categories:
                scores[cat] = random.uniform(5, 80)

            total = sum(
                scores[c] * w
                for c, w in DEFAULT_CATEGORY_WEIGHTS.items()
            )

            if total > 75:
                level = "CRITICAL"
            elif total > 50:
                level = "HIGH"
            elif total > 25:
                level = "MODERATE"
            else:
                level = "LOW"

            assessment = RiskAssessment(
                airport_code=code,
                airport_name=code,
                assessed_date=assessed,
                total_score=round(total, 2),
                risk_level=level,
            )
            session.add(assessment)
            await session.flush()

            for cat in categories:
                cat_record = CategoryScoreRecord(
                    assessment_id=assessment.id,
                    category_code=cat,
                    category_name=cat_names[cat],
                    score=round(scores[cat], 2),
                    level="MODERATE",
                    factors={"test_factor": round(scores[cat] * 0.5, 2)},
                )
                session.add(cat_record)

    await session.commit()


class TestWeightServiceNoData:
    """데이터 없는 상태에서의 동작"""

    @pytest.mark.asyncio
    async def test_get_active_weights_returns_none(self, db_session):
        service = WeightService(db_session)
        result = await service.get_active_weights()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_category_weights_returns_defaults(self, db_session):
        service = WeightService(db_session)
        weights = await service.get_active_category_weights()
        assert weights == DEFAULT_CATEGORY_WEIGHTS

    @pytest.mark.asyncio
    async def test_calculate_skips_insufficient_data(self, db_session):
        service = WeightService(db_session)
        result = await service.calculate_and_save_weights()
        assert result is None

    @pytest.mark.asyncio
    async def test_correlation_analysis_returns_error(self, db_session):
        service = WeightService(db_session)
        result = await service.run_correlation_analysis()
        assert "error" in result


class TestWeightServiceWithData:
    """충분한 데이터가 있는 상태에서의 동작"""

    @pytest_asyncio.fixture
    async def seeded_session(self, db_session):
        await _seed_risk_data(db_session, n_days=50, n_airports=5)
        return db_session

    @pytest.mark.asyncio
    async def test_calculate_ensemble_weights(self, seeded_session):
        """앙상블 가중치 산출 성공"""
        service = WeightService(seeded_session)
        result = await service.calculate_and_save_weights(method="ensemble")

        assert result is not None
        assert result.is_active is True
        assert result.method == "ensemble"
        assert abs(sum(result.category_weights.values()) - 1.0) < 0.02
        assert result.sample_size >= 30

    @pytest.mark.asyncio
    async def test_calculate_correlation_weights(self, seeded_session):
        """상관분석 기반 가중치 산출"""
        service = WeightService(seeded_session)
        result = await service.calculate_and_save_weights(method="correlation")

        assert result is not None
        assert result.method == "correlation"
        assert len(result.category_weights) == 6

    @pytest.mark.asyncio
    async def test_active_weights_updated(self, seeded_session):
        """산출 후 활성 가중치가 DB에서 조회됨"""
        service = WeightService(seeded_session)
        await service.calculate_and_save_weights(method="ensemble")

        active = await service.get_active_weights()
        assert active is not None
        assert active.is_active is True

        weights = await service.get_active_category_weights()
        assert weights != DEFAULT_CATEGORY_WEIGHTS  # 다를 수 있음 (랜덤 데이터)
        assert abs(sum(weights.values()) - 1.0) < 0.02

    @pytest.mark.asyncio
    async def test_recalculation_deactivates_old(self, seeded_session):
        """재산출 시 이전 가중치 비활성화"""
        service = WeightService(seeded_session)

        first = await service.calculate_and_save_weights(method="correlation")
        second = await service.calculate_and_save_weights(method="ensemble")

        assert first is not None
        assert second is not None

        # refresh first from DB
        await seeded_session.refresh(first)
        assert first.is_active is False
        assert second.is_active is True

    @pytest.mark.asyncio
    async def test_weight_history(self, seeded_session):
        """가중치 이력 조회"""
        service = WeightService(seeded_session)
        await service.calculate_and_save_weights(method="correlation")
        await service.calculate_and_save_weights(method="ensemble")

        history = await service.get_weight_history(limit=10)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_correlation_analysis(self, seeded_session):
        """상관분석 결과 반환"""
        service = WeightService(seeded_session)
        result = await service.run_correlation_analysis()

        assert "error" not in result
        assert "factor_correlations" in result
        assert "sample_size" in result
        assert result["sample_size"] >= 30


class TestRiskCalculatorDynamicWeights:
    """RiskCalculator 동적 가중치 테스트"""

    def test_custom_weights(self):
        from app.services.risk_calculator import RiskCalculator

        custom = {"weather": 0.50, "aviation": 0.10, "security": 0.10,
                  "health": 0.10, "operational": 0.10, "external": 0.10}
        calc = RiskCalculator(custom_weights=custom)
        assert calc.active_weights == custom
        assert calc.active_weights["weather"] == 0.50

    def test_no_custom_weights_uses_defaults(self):
        from app.services.risk_calculator import RiskCalculator

        calc = RiskCalculator()
        assert calc.active_weights == RiskCalculator.CATEGORY_WEIGHTS

    def test_class_constant_unchanged(self):
        from app.services.risk_calculator import RiskCalculator

        custom = {"weather": 0.50}
        calc = RiskCalculator(custom_weights=custom)
        # 클래스 상수는 변경되지 않음
        assert RiskCalculator.CATEGORY_WEIGHTS["weather"] == 0.20
