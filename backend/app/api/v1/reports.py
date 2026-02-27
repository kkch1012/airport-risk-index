"""
리포트 다운로드 API 엔드포인트
"""

import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth_dependencies import get_current_user
from app.core.constants import AIRPORT_NAMES
from app.models.user import User
from app.services.report_generator import ReportGenerator

router = APIRouter()


@router.get("/csv")
async def download_csv(
    airport_code: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """CSV 리포트 다운로드"""
    if airport_code:
        airport_code = airport_code.upper()
        if airport_code not in AIRPORT_NAMES:
            raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")
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
    _user: User = Depends(get_current_user),
):
    """Excel 리포트 다운로드"""
    if airport_code:
        airport_code = airport_code.upper()
        if airport_code not in AIRPORT_NAMES:
            raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")
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
    _user: User = Depends(get_current_user),
):
    """PDF 리포트 다운로드"""
    if airport_code:
        airport_code = airport_code.upper()
        if airport_code not in AIRPORT_NAMES:
            raise HTTPException(status_code=404, detail="공항을 찾을 수 없습니다.")
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
        # 파일명에 안전한 문자만 허용
        safe_code = re.sub(r"[^A-Za-z0-9]", "", airport_code)
        return f"risk_report_{safe_code}_{date_str}.{ext}"
    return f"risk_report_all_{date_str}.{ext}"
