"""
위험지수 이력 저장/조회 테스트
"""

import pytest
from datetime import date

from app.services.risk_calculator import RiskResult, CategoryScore
from app.services.risk_history_service import RiskHistoryService
from app.models.risk_history import RiskAssessment, CategoryScoreRecord


def _make_risk_result(airport_code: str = "ICN", assessed_date: str = "2025-01-15", total_score: float = 42.5) -> RiskResult:
    """테스트용 RiskResult 생성 헬퍼"""
    categories = {
        "weather": CategoryScore(code="weather", name="기상", score=35.0, level="MODERATE", factors={"wind": 10.0, "rain": 25.0}),
        "aviation": CategoryScore(code="aviation", name="항공안전", score=20.0, level="LOW", factors={"incidents": 5.0}),
        "security": CategoryScore(code="security", name="보안", score=30.0, level="MODERATE", factors={"advisory": 30.0}),
        "health": CategoryScore(code="health", name="보건", score=15.0, level="LOW", factors={"disease": 15.0}),
        "operational": CategoryScore(code="operational", name="운영", score=50.0, level="MODERATE", factors={"delay": 50.0}),
        "external": CategoryScore(code="external", name="외부", score=25.0, level="LOW", factors={"travel": 25.0}),
    }
    return RiskResult(
        airport_code=airport_code,
        airport_name="인천국제공항" if airport_code == "ICN" else airport_code,
        date=assessed_date,
        total_score=total_score,
        risk_level="MODERATE",
        categories=categories,
        updated_at="2025-01-15T12:00:00",
    )


@pytest.mark.asyncio
async def test_save_assessment(db_session):
    """단건 저장 테스트"""
    service = RiskHistoryService(db_session)
    result = _make_risk_result()

    assessment = await service.save_assessment(result)

    assert assessment is not None
    assert assessment.airport_code == "ICN"
    assert assessment.total_score == 42.5
    assert assessment.risk_level == "MODERATE"
    assert assessment.assessed_date == date(2025, 1, 15)


@pytest.mark.asyncio
async def test_save_assessment_creates_category_scores(db_session):
    """카테고리 점수도 함께 저장되는지 테스트"""
    service = RiskHistoryService(db_session)
    result = _make_risk_result()

    assessment = await service.save_assessment(result)

    # 카테고리 점수 조회
    from sqlalchemy import select
    stmt = select(CategoryScoreRecord).where(CategoryScoreRecord.assessment_id == assessment.id)
    rows = (await db_session.execute(stmt)).scalars().all()

    assert len(rows) == 6
    codes = {r.category_code for r in rows}
    assert codes == {"weather", "aviation", "security", "health", "operational", "external"}


@pytest.mark.asyncio
async def test_upsert_same_day(db_session):
    """같은 공항 같은 날짜에 두 번 저장하면 업데이트"""
    service = RiskHistoryService(db_session)

    # 첫 번째 저장
    result1 = _make_risk_result(total_score=40.0)
    await service.save_assessment(result1)

    # 두 번째 저장 (같은 날짜, 다른 점수)
    result2 = _make_risk_result(total_score=55.0)
    await service.save_assessment(result2)

    # 하나만 존재해야 함
    from sqlalchemy import select, func
    count = (await db_session.execute(
        select(func.count()).select_from(RiskAssessment)
    )).scalar()
    assert count == 1

    # 업데이트된 점수 확인
    latest = await service.get_latest("ICN")
    assert latest.total_score == 55.0


@pytest.mark.asyncio
async def test_save_batch(db_session):
    """일괄 저장 테스트"""
    service = RiskHistoryService(db_session)

    results = [
        _make_risk_result(airport_code="ICN", total_score=40.0),
        _make_risk_result(airport_code="GMP", total_score=35.0),
        _make_risk_result(airport_code="PUS", total_score=50.0),
    ]

    saved = await service.save_batch(results)
    assert saved == 3

    # 각각 조회
    for code in ["ICN", "GMP", "PUS"]:
        latest = await service.get_latest(code)
        assert latest is not None
        assert latest.airport_code == code


@pytest.mark.asyncio
async def test_get_history(db_session):
    """기간별 이력 조회 테스트"""
    service = RiskHistoryService(db_session)

    # 3일치 데이터 저장
    for day in range(13, 16):
        result = _make_risk_result(assessed_date=f"2025-01-{day}", total_score=30.0 + day)
        await service.save_assessment(result)

    history = await service.get_history("ICN", date(2025, 1, 13), date(2025, 1, 15))
    assert len(history) == 3
    # 날짜순 정렬
    assert history[0].assessed_date < history[2].assessed_date


@pytest.mark.asyncio
async def test_get_history_partial_range(db_session):
    """기간 범위 내 일부만 있는 경우"""
    service = RiskHistoryService(db_session)

    await service.save_assessment(_make_risk_result(assessed_date="2025-01-14"))

    history = await service.get_history("ICN", date(2025, 1, 13), date(2025, 1, 15))
    assert len(history) == 1
    assert history[0].assessed_date == date(2025, 1, 14)


@pytest.mark.asyncio
async def test_get_latest_empty(db_session):
    """데이터 없을 때 None 반환"""
    service = RiskHistoryService(db_session)
    latest = await service.get_latest("ICN")
    assert latest is None


@pytest.mark.asyncio
async def test_get_latest(db_session):
    """최신 평가 조회"""
    service = RiskHistoryService(db_session)

    await service.save_assessment(_make_risk_result(assessed_date="2025-01-10", total_score=30.0))
    await service.save_assessment(_make_risk_result(assessed_date="2025-01-15", total_score=50.0))
    await service.save_assessment(_make_risk_result(assessed_date="2025-01-12", total_score=40.0))

    latest = await service.get_latest("ICN")
    assert latest.assessed_date == date(2025, 1, 15)
    assert latest.total_score == 50.0
