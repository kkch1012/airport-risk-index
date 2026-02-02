"""
데이터베이스 연결 및 세션 관리
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# 비동기 엔진 생성
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
)

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
    """데이터베이스 초기화"""
    async with engine.begin() as conn:
        # 테이블 생성 (개발용, 프로덕션에서는 Alembic 사용)
        # await conn.run_sync(Base.metadata.create_all)
        pass


async def get_db() -> AsyncSession:
    """의존성 주입용 DB 세션 생성기"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
