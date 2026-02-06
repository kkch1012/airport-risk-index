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

class TestReportAPI:

    def test_csv_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/reports/csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    def test_excel_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/reports/excel")
        assert resp.status_code == 200
        assert "spreadsheet" in resp.headers.get("content-type", "")

    def test_pdf_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/reports/pdf")
        assert resp.status_code == 200
        assert "pdf" in resp.headers.get("content-type", "")

    def test_csv_with_airport_filter(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/reports/csv?airport_code=ICN")
        assert resp.status_code == 200

    def test_content_disposition_header(self):
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/reports/csv")
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
