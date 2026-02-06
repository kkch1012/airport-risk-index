"""
리포트 다운로드 API 엔드포인트
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.report_generator import ReportGenerator

router = APIRouter()


@router.get("/csv")
async def download_csv(
    airport_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """CSV 리포트 다운로드"""
    generator = ReportGenerator(db)
    content = await generator.generate_csv(airport_code)
    filename = _make_filename("csv", airport_code)

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/excel")
async def download_excel(
    airport_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Excel 리포트 다운로드"""
    generator = ReportGenerator(db)
    content = await generator.generate_excel(airport_code)
    filename = _make_filename("xlsx", airport_code)

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf")
async def download_pdf(
    airport_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """PDF 리포트 다운로드"""
    generator = ReportGenerator(db)
    content = await generator.generate_pdf(airport_code)
    filename = _make_filename("pdf", airport_code)

    return StreamingResponse(
        iter([content]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _make_filename(ext: str, airport_code: Optional[str]) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    if airport_code:
        return f"risk_report_{airport_code}_{date_str}.{ext}"
    return f"risk_report_all_{date_str}.{ext}"
