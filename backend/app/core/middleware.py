"""
HTTP 요청 미들웨어

- 접근 로그 (method, path, status, duration_ms)
- Prometheus 히스토그램 메트릭 (prometheus_client 미설치 시 graceful skip)
"""

import logging
import re
import time
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# /health, /metrics 경로는 접근 로그에서 제외
EXCLUDED_PATHS = {"/health", "/metrics"}

# Prometheus 히스토그램 (선택적)
_histogram: Optional[object] = None

try:
    from prometheus_client import Histogram

    _histogram = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration in seconds",
        labelnames=["method", "path", "status"],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
except ImportError:
    pass


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """요청 타이밍 + 접근 로그 + Prometheus 메트릭"""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        path = request.url.path
        method = request.method
        status = response.status_code

        # Prometheus 메트릭 기록 (경로 정규화로 카디널리티 폭발 방지)
        if _histogram is not None:
            normalized = re.sub(r'/airports/[A-Za-z]{2,4}', '/airports/{code}', path)
            normalized = re.sub(r'/\d+', '/{id}', normalized)
            _histogram.labels(method=method, path=normalized, status=status).observe(duration)

        # 접근 로그 (노이즈 경로 제외)
        if path not in EXCLUDED_PATHS:
            logger.info(
                "request",
                extra={
                    "method": method,
                    "path": path,
                    "status": status,
                    "duration_ms": round(duration * 1000, 1),
                    "client": request.client.host if request.client else "-",
                },
            )

        return response
