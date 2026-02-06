"""
데이터베이스 연결 및 세션 관리
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# 비동기 엔진 생성 (SQLite는 pool_size/max_overflow 미지원)
engine_kwargs = {
    "echo": settings.DEBUG,
}
if not settings.USE_SQLITE:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# 비동기 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# 베이스 클래스
class Base(DeclarativeBase):
    pass


async def init_db():
    """데이터베이스 초기화 (개발환경: 자동 테이블 생성)"""
    # 모델 import하여 Base.metadata에 등록
    import app.models.risk_history  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """의존성 주입용 DB 세션 생성기"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
