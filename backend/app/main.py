"""
공항 위험지수 모니터링 시스템 - FastAPI 메인 애플리케이션
"""

import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.v1.router import api_router
from app.api.v1.metrics import router as metrics_router
from app.core.logging_config import setup_logging
from app.core.middleware import RequestTimingMiddleware

# 구조화 로깅 초기화 (stdlib root logger 래핑)
setup_logging(env=settings.ENV)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 이벤트 핸들러"""
    # 개발환경: DB 테이블 자동 생성
    if settings.USE_SQLITE:
        from app.core.database import init_db
        try:
            await init_db()
            logger.info("Database tables initialized")
        except Exception:
            logger.exception("Failed to initialize database tables")

    # Redis Pub/Sub → WebSocket 브릿지 시작
    import asyncio
    from app.core.redis_pubsub import start_redis_subscriber
    from app.core.websocket_manager import manager

    async def _on_risk_update(data: dict):
        await manager.broadcast_all(data)

    subscriber_task = asyncio.create_task(start_redis_subscriber(_on_risk_update))
    logger.info("Redis → WebSocket subscriber started")

    yield

    subscriber_task.cancel()


# FastAPI 앱 생성
app = FastAPI(
    title="공항 위험지수 모니터링 시스템",
    description="실시간 공항 위험요인 수집 및 통합 위험지수 산출 API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url="/redoc" if settings.ENV != "production" else None,
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# 요청 타이밍 + 접근 로그 미들웨어
app.add_middleware(RequestTimingMiddleware)

# API 라우터 등록
app.include_router(api_router, prefix="/api/v1")

# Prometheus 메트릭 (루트 레벨)
app.include_router(metrics_router)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "name": "공항 위험지수 모니터링 시스템",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }


# 전역 예외 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """전역 예외 핸들러"""
    logger.exception("Unhandled exception: %s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "서버 오류가 발생했습니다.",
        },
    )
