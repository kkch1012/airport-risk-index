"""
pytest 설정 및 공통 fixture
"""

import os

# 테스트 시 SQLite 사용 강제 (asyncpg 불필요)
os.environ.setdefault("USE_SQLITE", "true")

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.database import Base
from app.main import app


@pytest.fixture
def client():
    """FastAPI 테스트 클라이언트"""
    return TestClient(app)


@pytest.fixture
def airport_codes():
    """테스트용 공항 코드 목록"""
    return ["ICN", "GMP", "PUS", "CJU", "TAE"]


@pytest_asyncio.fixture
async def db_session():
    """인메모리 SQLite 기반 비동기 DB 세션 (테스트용)"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    # 모델 import → 메타데이터 등록
    import app.models.risk_history  # noqa: F401
    import app.models.weight_history  # noqa: F401
    import app.models.international_incident  # noqa: F401
    import app.models.news_article  # noqa: F401
    import app.models.user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
