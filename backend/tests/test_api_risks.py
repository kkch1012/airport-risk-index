"""
위험지수 API 엔드포인트 테스트
"""

import pytest


class TestHealthCheck:
    """헬스체크 엔드포인트 테스트"""

    def test_health_check(self, client):
        """헬스체크 응답 확인"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_root(self, client):
        """루트 엔드포인트 확인"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data


class TestDashboardAPI:
    """대시보드 API 테스트"""

    def test_dashboard_returns_200(self, client):
        """대시보드 API가 200 응답을 반환하는지 확인"""
        response = client.get("/api/v1/risks/dashboard")
        assert response.status_code == 200

    def test_dashboard_structure(self, client):
        """대시보드 응답 구조 확인"""
        response = client.get("/api/v1/risks/dashboard")
        data = response.json()

        # 필수 필드 확인
        assert "summary" in data
        assert "airports" in data
        assert "alerts" in data
        assert "data_sources" in data

    def test_dashboard_summary_fields(self, client):
        """대시보드 요약 필드 확인"""
        response = client.get("/api/v1/risks/dashboard")
        data = response.json()
        summary = data["summary"]

        assert "total_airports" in summary
        assert "high_risk_count" in summary
        assert "average_score" in summary
        assert "updated_at" in summary

        # 값 범위 확인
        assert summary["total_airports"] > 0
        assert summary["high_risk_count"] >= 0
        assert 0 <= summary["average_score"] <= 100

    def test_dashboard_airports_list(self, client):
        """대시보드 공항 목록 확인"""
        response = client.get("/api/v1/risks/dashboard")
        data = response.json()
        airports = data["airports"]

        assert len(airports) > 0

        # 첫 번째 공항 구조 확인
        airport = airports[0]
        assert "code" in airport
        assert "name" in airport
        assert "score" in airport
        assert "level" in airport

        # 점수 범위 확인
        assert 0 <= airport["score"] <= 100
        assert airport["level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]


class TestAirportDetailAPI:
    """공항 상세 API 테스트"""

    def test_airport_detail_icn(self, client):
        """인천공항 상세 정보 조회"""
        response = client.get("/api/v1/risks/airports/ICN")
        assert response.status_code == 200

        data = response.json()
        assert data["airport"]["code"] == "ICN"
        assert "total_score" in data
        assert "risk_level" in data
        assert "categories" in data

    def test_airport_detail_categories(self, client):
        """공항 상세 카테고리 확인"""
        response = client.get("/api/v1/risks/airports/ICN")
        data = response.json()
        categories = data["categories"]

        # 6개 카테고리 확인
        expected_categories = ["weather", "external", "health", "operational", "aviation", "security"]
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
            assert "name" in categories[cat]
            assert "score" in categories[cat]
            assert "level" in categories[cat]
            assert 0 <= categories[cat]["score"] <= 100
            # 데이터 신뢰도 플래그 노출 확인
            assert "has_data" in categories[cat]
            assert "is_proxy" in categories[cat]
            assert isinstance(categories[cat]["has_data"], bool)
            assert isinstance(categories[cat]["is_proxy"], bool)

    def test_airport_detail_invalid_code(self, client):
        """존재하지 않는 공항 코드"""
        response = client.get("/api/v1/risks/airports/XXX")
        assert response.status_code == 404

    @pytest.mark.parametrize("airport_code", ["ICN", "GMP", "PUS", "CJU", "TAE"])
    def test_multiple_airports(self, client, airport_code):
        """여러 공항 조회 테스트"""
        response = client.get(f"/api/v1/risks/airports/{airport_code}")
        assert response.status_code == 200
        data = response.json()
        assert data["airport"]["code"] == airport_code


class TestHealthRiskAPI:
    """보건위험 API 테스트"""

    def test_health_risk_list(self, client):
        """보건위험 목록 조회"""
        response = client.get("/api/v1/risks/health-risk")
        assert response.status_code == 200

        data = response.json()
        assert "summary" in data
        assert "data_source" in data

    def test_health_risk_airport(self, client):
        """공항별 보건위험 조회"""
        response = client.get("/api/v1/risks/health-risk/airports/ICN")
        assert response.status_code == 200


class TestFlightStatusAPI:
    """운항정보 API 테스트"""

    def test_flight_status_list(self, client):
        """운항정보 목록 조회"""
        response = client.get("/api/v1/risks/flight-status")
        assert response.status_code == 200

        data = response.json()
        assert "summary" in data
        assert "airports" in data

    def test_flight_status_airport(self, client):
        """공항별 운항정보 조회"""
        response = client.get("/api/v1/risks/flight-status/airports/GMP")
        assert response.status_code == 200


class TestTravelAdvisoryAPI:
    """여행경보 API 테스트"""

    def test_travel_advisory_list(self, client):
        """여행경보 목록 조회"""
        response = client.get("/api/v1/risks/travel-advisory")
        assert response.status_code == 200

        data = response.json()
        assert "summary" in data
        assert "data_source" in data


class TestComparisonAPI:
    """공항 비교 API 테스트"""

    def test_compare_airports(self, client):
        """공항 비교 API"""
        # FastAPI Query(List[str])는 파라미터를 여러 번 전달해야 함
        response = client.get("/api/v1/risks/comparison?airport_codes=ICN&airport_codes=GMP&airport_codes=PUS")
        assert response.status_code == 200

        data = response.json()
        assert "comparison" in data
        assert len(data["comparison"]) == 3
