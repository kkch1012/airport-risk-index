"""
Prometheus 메트릭 엔드포인트

GET /metrics → Prometheus 텍스트 형식 노출
prometheus_client 미설치 시 503 반환
"""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Prometheus 메트릭"""
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        return PlainTextResponse(
            content=generate_latest().decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )
    except ImportError:
        return PlainTextResponse(
            content="prometheus_client not installed",
            status_code=503,
        )
