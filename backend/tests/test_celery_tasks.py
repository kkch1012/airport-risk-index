"""
Celery 태스크 테스트 (Redis/Celery 브로커 없이 함수 직접 호출)
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.risk_calculator import RiskResult, CategoryScore
from app.core.constants import AIRPORT_NAMES


def _make_weather_map():
    """테스트용 기상 데이터 맵"""
    return {
        code: {
            "temperature": 15.0,
            "wind_speed": 5.0,
            "visibility": 10000,
            "precipitation": 0,
        }
        for code in AIRPORT_NAMES
    }


def _make_advisory_data():
    """테스트용 여행경보 데이터"""
    return [
        {"country_name": "테스트국", "country_code": "TS", "country_iso": "TS", "alarm_level": 1, "alarm_name": "경계"},
    ]


def _make_health_data():
    """테스트용 보건 데이터"""
    return [
        {"country_name": "테스트국", "disease_name": "테스트질병", "risk_score": 30},
    ]


def _make_operational_data():
    """테스트용 운항 데이터"""
    return [
        {"airport_code": "ICN", "total_flights": 100, "delayed_flights": 5, "cancelled_flights": 1},
    ]


def _make_aviation_data():
    """테스트용 항공안전 데이터"""
    return [
        {"title": "테스트 사고보고서", "date": "2025-01-01", "severity": "minor"},
    ]


def _make_risk_result(airport_code="ICN", total_score=42.5):
    """테스트용 RiskResult"""
    categories = {
        "weather": CategoryScore(code="weather", name="기상", score=35.0, level="MODERATE", factors={}),
        "aviation": CategoryScore(code="aviation", name="항공안전", score=20.0, level="LOW", factors={}),
        "security": CategoryScore(code="security", name="보안", score=30.0, level="MODERATE", factors={}),
        "health": CategoryScore(code="health", name="보건", score=15.0, level="LOW", factors={}),
        "operational": CategoryScore(code="operational", name="운영", score=50.0, level="MODERATE", factors={}),
        "external": CategoryScore(code="external", name="외부", score=25.0, level="LOW", factors={}),
    }
    return RiskResult(
        airport_code=airport_code,
        airport_name=AIRPORT_NAMES.get(airport_code, airport_code),
        date="2025-01-15",
        total_score=total_score,
        risk_level="MODERATE",
        categories=categories,
        updated_at="2025-01-15T12:00:00",
    )


# --- 유틸리티 테스트 ---


class TestRunAsync:
    """run_async 브릿지 테스트"""

    def test_run_async_executes_coroutine(self):
        """async 코루틴이 sync 환경에서 실행되는지 확인"""
        from app.tasks.utils import run_async

        async def _simple():
            return 42

        result = run_async(_simple())
        assert result == 42

    def test_run_async_propagates_exception(self):
        """예외가 정상적으로 전파되는지 확인"""
        from app.tasks.utils import run_async

        async def _failing():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_async(_failing())


# --- 수집 유틸 함수 테스트 ---


class TestCollectUtils:
    """tasks/utils.py 수집 래퍼 함수 테스트"""

    @pytest.mark.asyncio
    async def test_collect_weather_success(self):
        """기상 수집 성공"""
        mock_result = {
            "status": "success",
            "data": [
                {"airport_code": "ICN", "weather": {"temperature": 15.0}},
                {"airport_code": "GMP", "weather": {"temperature": 12.0}},
            ],
        }

        with patch("app.tasks.utils.WeatherCollector") as MockCollector:
            instance = AsyncMock()
            instance.run.return_value = mock_result
            MockCollector.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockCollector.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.utils import collect_weather
            result = await collect_weather()

        assert "ICN" in result
        assert result["ICN"]["temperature"] == 15.0
        assert "GMP" in result

    @pytest.mark.asyncio
    async def test_collect_weather_failure_returns_empty(self):
        """기상 수집 실패 시 빈 딕셔너리 반환"""
        mock_result = {"status": "error", "error": "API timeout"}

        with patch("app.tasks.utils.WeatherCollector") as MockCollector:
            instance = AsyncMock()
            instance.run.return_value = mock_result
            MockCollector.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockCollector.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.utils import collect_weather
            result = await collect_weather()

        assert result == {}

    @pytest.mark.asyncio
    async def test_collect_travel_advisory_success(self):
        """여행경보 수집 성공"""
        mock_data = [{"country_name": "일본", "alarm_level": 1}]
        mock_result = {"status": "success", "data": mock_data}

        with patch("app.tasks.utils.TravelAdvisoryCollector") as MockCollector:
            instance = AsyncMock()
            instance.run.return_value = mock_result
            instance.api_key = "test-key"
            MockCollector.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockCollector.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.utils import collect_travel_advisory
            data, is_real = await collect_travel_advisory()

        assert len(data) == 1
        assert is_real is True

    @pytest.mark.asyncio
    async def test_collect_travel_advisory_failure(self):
        """여행경보 수집 실패 시 빈 리스트 반환"""
        mock_result = {"status": "error", "error": "timeout"}

        with patch("app.tasks.utils.TravelAdvisoryCollector") as MockCollector:
            instance = AsyncMock()
            instance.run.return_value = mock_result
            MockCollector.return_value.__aenter__ = AsyncMock(return_value=instance)
            MockCollector.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.utils import collect_travel_advisory
            data, is_real = await collect_travel_advisory()

        assert data == []
        assert is_real is False


# --- 파이프라인 테스트 ---


class TestCollectAndCalculatePipeline:
    """전체 수집 → 계산 → 저장 파이프라인 테스트"""

    @pytest.mark.asyncio
    async def test_pipeline_full(self, db_session):
        """전체 파이프라인이 수집 → 계산 → DB 저장까지 동작"""
        weather_map = _make_weather_map()
        advisory_data = _make_advisory_data()
        health_data = _make_health_data()
        operational_data = _make_operational_data()
        aviation_data = _make_aviation_data()

        with (
            patch("app.tasks.collect_risks.collect_weather", new_callable=AsyncMock, return_value=weather_map),
            patch("app.tasks.collect_risks.collect_travel_advisory", new_callable=AsyncMock, return_value=(advisory_data, True)),
            patch("app.tasks.collect_risks.collect_health", new_callable=AsyncMock, return_value=(health_data, True)),
            patch("app.tasks.collect_risks.collect_operational", new_callable=AsyncMock, return_value=(operational_data, True)),
            patch("app.tasks.collect_risks.collect_aviation", new_callable=AsyncMock, return_value=(aviation_data, True)),
            patch("app.tasks.collect_risks.AsyncSessionLocal") as MockSession,
        ):
            # DB 세션 mock → 실제 db_session 사용
            MockSession.return_value.__aenter__ = AsyncMock(return_value=db_session)
            MockSession.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.collect_risks import _collect_and_calculate
            result = await _collect_and_calculate()

        assert result["airports"] == len(AIRPORT_NAMES)
        assert result["saved"] == len(AIRPORT_NAMES)
        assert "high_risk" in result

    @pytest.mark.asyncio
    async def test_pipeline_calculates_all_airports(self):
        """15개 공항 모두 계산하는지 확인"""
        weather_map = _make_weather_map()

        with (
            patch("app.tasks.collect_risks.collect_weather", new_callable=AsyncMock, return_value=weather_map),
            patch("app.tasks.collect_risks.collect_travel_advisory", new_callable=AsyncMock, return_value=([], False)),
            patch("app.tasks.collect_risks.collect_health", new_callable=AsyncMock, return_value=([], False)),
            patch("app.tasks.collect_risks.collect_operational", new_callable=AsyncMock, return_value=([], False)),
            patch("app.tasks.collect_risks.collect_aviation", new_callable=AsyncMock, return_value=([], False)),
            patch("app.tasks.collect_risks.AsyncSessionLocal") as MockSession,
            patch("app.tasks.collect_risks.RiskHistoryService") as MockService,
        ):
            mock_svc = AsyncMock()
            mock_svc.save_batch.return_value = 15
            MockService.return_value = mock_svc
            MockSession.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            MockSession.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.tasks.collect_risks import _collect_and_calculate
            result = await _collect_and_calculate()

        assert result["airports"] == 15
        assert result["saved"] == 15


# --- Celery 태스크 함수 직접 호출 테스트 ---


class TestCeleryTasks:
    """Celery 태스크 함수 직접 호출 (브로커 없이)"""

    def test_collect_and_calculate_all_risks_runs(self):
        """전체 수집+계산 태스크가 run_async로 실행"""
        from app.tasks.collect_risks import collect_and_calculate_all_risks

        with patch("app.tasks.collect_risks.run_async") as mock_run:
            mock_run.return_value = {"airports": 15, "saved": 15, "high_risk": 0}
            # .run() 으로 Celery 데코레이터를 우회하여 원본 함수 실행
            result = collect_and_calculate_all_risks.run()

        assert result["airports"] == 15
        mock_run.assert_called_once()

    def test_collect_weather_data_runs(self):
        """기상 수집 태스크 실행"""
        from app.tasks.collect_risks import collect_weather_data

        with patch("app.tasks.collect_risks.run_async") as mock_run:
            mock_run.return_value = {"airports_collected": 15}
            result = collect_weather_data.run()

        assert result["airports_collected"] == 15

    def test_collect_advisory_data_runs(self):
        """여행경보 수집 태스크 실행"""
        from app.tasks.collect_risks import collect_advisory_data

        with patch("app.tasks.collect_risks.run_async") as mock_run:
            mock_run.return_value = {"countries_collected": 10, "is_real_data": True}
            result = collect_advisory_data.run()

        assert result["countries_collected"] == 10

    def test_task_retries_on_exception(self):
        """예외 발생 시 retry 호출"""
        from app.tasks.collect_risks import collect_and_calculate_all_risks

        with patch("app.tasks.collect_risks.run_async") as mock_run:
            mock_run.side_effect = ConnectionError("Redis down")

            with patch.object(collect_and_calculate_all_risks, "retry", side_effect=ConnectionError("retry")) as mock_retry:
                with pytest.raises(ConnectionError):
                    collect_and_calculate_all_risks.run()

                mock_retry.assert_called_once()


# --- Constants 테스트 ---


class TestConstants:
    """공유 상수 테스트"""

    def test_airport_names_count(self):
        """15개 공항이 정의되어 있는지"""
        assert len(AIRPORT_NAMES) == 15

    def test_airport_names_has_major_airports(self):
        """주요 공항 포함 확인"""
        assert "ICN" in AIRPORT_NAMES
        assert "GMP" in AIRPORT_NAMES
        assert "PUS" in AIRPORT_NAMES
        assert "CJU" in AIRPORT_NAMES

    def test_risks_api_uses_shared_constants(self):
        """risks.py가 공유 AIRPORT_NAMES를 사용하는지"""
        from app.api.v1 import risks
        # risks 모듈에 로컬 AIRPORT_NAMES가 없고 constants에서 가져와야 함
        assert risks.AIRPORT_NAMES is AIRPORT_NAMES
