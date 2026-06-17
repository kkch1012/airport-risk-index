"""
리포트 생성 테스트
"""

import pytest
from datetime import date

from app.services.report_generator import ReportGenerator, CATEGORY_LABELS, LEVEL_LABELS
from app.models.risk_history import RiskAssessment, CategoryScoreRecord


# ─── 헬퍼 ─────────────────────────────────────

async def _seed_data(session):
    """테스트용 데이터 삽입"""
    assessment = RiskAssessment(
        airport_code="ICN",
        airport_name="인천국제공항",
        assessed_date=date(2026, 2, 1),
        total_score=45.5,
        risk_level="MODERATE",
    )
    session.add(assessment)
    await session.flush()

    for cat, score in [
        ("weather", 30.0),
        ("aviation", 50.0),
        ("security", 20.0),
        ("health", 15.0),
        ("operational", 60.0),
        ("external", 40.0),
    ]:
        session.add(CategoryScoreRecord(
            assessment_id=assessment.id,
            category_code=cat,
            category_name=CATEGORY_LABELS.get(cat, cat),
            score=score,
            level="LOW" if score < 30 else "MODERATE",
            factors={},
        ))

    await session.commit()
    return assessment


# ─── CSV 테스트 ────────────────────────────────

class TestCSVReport:

    @pytest.mark.asyncio
    async def test_generate_csv_empty(self, db_session):
        gen = ReportGenerator(db_session)
        content = await gen.generate_csv()
        assert isinstance(content, bytes)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_generate_csv_with_data(self, db_session):
        await _seed_data(db_session)
        gen = ReportGenerator(db_session)
        content = await gen.generate_csv()
        text = content.decode("utf-8-sig")
        assert "ICN" in text or "공항코드" in text

    @pytest.mark.asyncio
    async def test_generate_csv_filtered(self, db_session):
        await _seed_data(db_session)
        gen = ReportGenerator(db_session)
        content = await gen.generate_csv(airport_code="ICN")
        text = content.decode("utf-8-sig")
        assert "ICN" in text or "인천" in text

    @pytest.mark.asyncio
    async def test_csv_has_header_row(self, db_session):
        await _seed_data(db_session)
        gen = ReportGenerator(db_session)
        content = await gen.generate_csv()
        text = content.decode("utf-8-sig")
        lines = text.strip().split("\n")
        assert len(lines) >= 2  # 헤더 + 데이터

    @pytest.mark.asyncio
    async def test_csv_confidence_note(self, db_session):
        """추정치(is_proxy)·데이터없음(has_data=False)이 신뢰도비고에 표기"""
        assessment = RiskAssessment(
            airport_code="GMP",
            airport_name="김포국제공항",
            assessed_date=date(2026, 2, 2),
            total_score=20.0,
            risk_level="LOW",
        )
        db_session.add(assessment)
        await db_session.flush()
        db_session.add(CategoryScoreRecord(
            assessment_id=assessment.id, category_code="operational",
            category_name="운영위험", score=18.0, level="LOW", factors={},
            has_data=True, is_proxy=True,
        ))
        db_session.add(CategoryScoreRecord(
            assessment_id=assessment.id, category_code="security",
            category_name="보안위협", score=0.0, level="LOW", factors={},
            has_data=False, is_proxy=False,
        ))
        await db_session.commit()

        gen = ReportGenerator(db_session)
        text = (await gen.generate_csv(airport_code="GMP")).decode("utf-8-sig")
        assert "신뢰도비고" in text
        assert "추정" in text
        assert "데이터없음" in text


# ─── Excel 테스트 ──────────────────────────────

class TestExcelReport:

    @pytest.mark.asyncio
    async def test_generate_excel_empty(self, db_session):
        gen = ReportGenerator(db_session)
        content = await gen.generate_excel()
        assert isinstance(content, bytes)
        # Excel 파일 시그니처 (PK zip)
        assert content[:2] == b"PK"

    @pytest.mark.asyncio
    async def test_generate_excel_with_data(self, db_session):
        await _seed_data(db_session)
        gen = ReportGenerator(db_session)
        content = await gen.generate_excel()
        assert content[:2] == b"PK"
        assert len(content) > 100

    @pytest.mark.asyncio
    async def test_generate_excel_filtered(self, db_session):
        await _seed_data(db_session)
        gen = ReportGenerator(db_session)
        content = await gen.generate_excel(airport_code="ICN")
        assert isinstance(content, bytes)


# ─── PDF 테스트 ────────────────────────────────

class TestPDFReport:

    @pytest.mark.asyncio
    async def test_generate_pdf_empty(self, db_session):
        gen = ReportGenerator(db_session)
        content = await gen.generate_pdf()
        assert isinstance(content, bytes)
        assert content[:4] == b"%PDF"

    @pytest.mark.asyncio
    async def test_generate_pdf_with_data(self, db_session):
        await _seed_data(db_session)
        gen = ReportGenerator(db_session)
        content = await gen.generate_pdf()
        assert content[:4] == b"%PDF"
        assert len(content) > 100

    @pytest.mark.asyncio
    async def test_generate_pdf_filtered(self, db_session):
        await _seed_data(db_session)
        gen = ReportGenerator(db_session)
        content = await gen.generate_pdf(airport_code="ICN")
        assert content[:4] == b"%PDF"


# ─── API 엔드포인트 테스트 ──────────────────────

def _get_auth_header(client):
    """테스트용 JWT 토큰 발급 헬퍼"""
    client.post("/api/v1/auth/register", json={
        "email": "reporttest@example.com",
        "username": "reporttest",
        "password": "password123",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "reporttest",
        "password": "password123",
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestReportAPI:

    def test_csv_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        headers = _get_auth_header(client)
        resp = client.get("/api/v1/reports/csv", headers=headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_excel_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        headers = _get_auth_header(client)
        resp = client.get("/api/v1/reports/excel", headers=headers)
        assert resp.status_code == 200
        assert "spreadsheet" in resp.headers.get("content-type", "")

    def test_pdf_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        headers = _get_auth_header(client)
        resp = client.get("/api/v1/reports/pdf", headers=headers)
        assert resp.status_code == 200
        assert "pdf" in resp.headers.get("content-type", "")

    def test_csv_with_airport_filter(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        headers = _get_auth_header(client)
        resp = client.get("/api/v1/reports/csv?airport_code=ICN", headers=headers)
        assert resp.status_code == 200

    def test_content_disposition_header(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        headers = _get_auth_header(client)
        resp = client.get("/api/v1/reports/csv", headers=headers)
        assert "content-disposition" in resp.headers
        assert "risk_report" in resp.headers["content-disposition"]


# ─── 유틸리티 테스트 ───────────────────────────

class TestReportUtils:

    def test_category_labels_coverage(self):
        for cat in ["weather", "aviation", "security", "health", "operational", "external"]:
            assert cat in CATEGORY_LABELS

    def test_level_labels_coverage(self):
        for level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            assert level in LEVEL_LABELS
