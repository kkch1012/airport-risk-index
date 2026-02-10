"""
인증 시스템 테스트 (서비스 + API)
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_user,
    get_user_by_email,
    get_user_by_username,
    authenticate_user,
)


# ===========================================
# Fixtures
# ===========================================

@pytest_asyncio.fixture
async def auth_db():
    """인증 테스트용 인메모리 DB 세션"""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    import app.models.user  # noqa: F401
    import app.models.risk_history  # noqa: F401
    import app.models.weight_history  # noqa: F401
    import app.models.international_incident  # noqa: F401
    import app.models.news_article  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def auth_client(auth_db):
    """인증 테스트용 FastAPI 클라이언트 (DB 오버라이드)"""
    # auth_db는 async fixture이므로 새 엔진/세션 필요
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(sync_engine)
    SyncSession = sessionmaker(sync_engine, expire_on_commit=False)

    # 동기 DB 오버라이드 (TestClient는 동기)
    async_engine = None

    async def override_get_db():
        _engine = create_async_engine("sqlite+aiosqlite://", echo=False)

        import app.models.user  # noqa: F401
        import app.models.risk_history  # noqa: F401
        import app.models.weight_history  # noqa: F401
        import app.models.international_incident  # noqa: F401
        import app.models.news_article  # noqa: F401

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield session

        await _engine.dispose()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def persistent_auth_client():
    """영속적 DB를 가진 인증 테스트 클라이언트 (회원가입 → 로그인 연계 테스트)"""
    import asyncio

    _engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async def _init():
        import app.models.user  # noqa: F401
        import app.models.risk_history  # noqa: F401
        import app.models.weight_history  # noqa: F401
        import app.models.international_incident  # noqa: F401
        import app.models.news_article  # noqa: F401

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_init())

    factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

    asyncio.get_event_loop().run_until_complete(_engine.dispose())


# ===========================================
# 비밀번호 해싱 테스트
# ===========================================

class TestPasswordHashing:
    def test_hash_password(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2  # bcrypt 솔트가 다름


# ===========================================
# JWT 토큰 테스트
# ===========================================

class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(data={"sub": "42"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert "exp" in payload

    def test_decode_invalid_token(self):
        payload = decode_access_token("invalid.token.here")
        assert payload is None

    def test_decode_expired_token(self):
        from datetime import timedelta
        token = create_access_token(data={"sub": "1"}, expires_delta=timedelta(seconds=-1))
        payload = decode_access_token(token)
        assert payload is None


# ===========================================
# 사용자 CRUD 테스트 (async)
# ===========================================

class TestUserCRUD:
    @pytest.mark.asyncio
    async def test_create_user(self, auth_db):
        user = await create_user(auth_db, "test@example.com", "testuser", "password123")
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.hashed_password != "password123"
        assert user.is_active is True
        assert user.is_admin is False

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, auth_db):
        await create_user(auth_db, "test@example.com", "testuser", "password123")
        user = await get_user_by_email(auth_db, "test@example.com")
        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, auth_db):
        user = await get_user_by_email(auth_db, "nobody@example.com")
        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, auth_db):
        await create_user(auth_db, "test@example.com", "testuser", "password123")
        user = await get_user_by_username(auth_db, "testuser")
        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self, auth_db):
        user = await get_user_by_username(auth_db, "nobody")
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, auth_db):
        await create_user(auth_db, "test@example.com", "testuser", "password123")
        user = await authenticate_user(auth_db, "testuser", "password123")
        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, auth_db):
        await create_user(auth_db, "test@example.com", "testuser", "password123")
        user = await authenticate_user(auth_db, "testuser", "wrongpassword")
        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_user_nonexistent(self, auth_db):
        user = await authenticate_user(auth_db, "nobody", "password123")
        assert user is None


# ===========================================
# 인증 API 테스트
# ===========================================

class TestAuthAPI:
    def test_register_success(self, persistent_auth_client):
        resp = persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "username": "newuser",
            "password": "password123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["username"] == "newuser"
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, persistent_auth_client):
        persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "dup@example.com",
            "username": "user1",
            "password": "password123",
        })
        resp = persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "dup@example.com",
            "username": "user2",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_duplicate_username(self, persistent_auth_client):
        persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "a@example.com",
            "username": "dupname",
            "password": "password123",
        })
        resp = persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "b@example.com",
            "username": "dupname",
            "password": "password123",
        })
        assert resp.status_code == 409

    def test_register_short_password(self, persistent_auth_client):
        resp = persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "short@example.com",
            "username": "shortpw",
            "password": "1234567",
        })
        assert resp.status_code == 422

    def test_register_invalid_email(self, persistent_auth_client):
        resp = persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "username": "bademail",
            "password": "password123",
        })
        assert resp.status_code == 422

    def test_login_success(self, persistent_auth_client):
        persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "password123",
        })
        resp = persistent_auth_client.post("/api/v1/auth/login", json={
            "username": "loginuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, persistent_auth_client):
        persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "wrong@example.com",
            "username": "wrongpw",
            "password": "password123",
        })
        resp = persistent_auth_client.post("/api/v1/auth/login", json={
            "username": "wrongpw",
            "password": "badpassword",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, persistent_auth_client):
        resp = persistent_auth_client.post("/api/v1/auth/login", json={
            "username": "ghost",
            "password": "password123",
        })
        assert resp.status_code == 401

    def test_get_me_with_token(self, persistent_auth_client):
        persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "me@example.com",
            "username": "meuser",
            "password": "password123",
        })
        login_resp = persistent_auth_client.post("/api/v1/auth/login", json={
            "username": "meuser",
            "password": "password123",
        })
        token = login_resp.json()["access_token"]

        resp = persistent_auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "meuser"
        assert data["email"] == "me@example.com"

    def test_get_me_without_token(self, persistent_auth_client):
        resp = persistent_auth_client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    def test_get_me_invalid_token(self, persistent_auth_client):
        resp = persistent_auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


# ===========================================
# Reports 인증 보호 테스트
# ===========================================

class TestReportsAuth:
    def test_csv_without_token(self, persistent_auth_client):
        resp = persistent_auth_client.get("/api/v1/reports/csv")
        assert resp.status_code in (401, 403)

    def test_excel_without_token(self, persistent_auth_client):
        resp = persistent_auth_client.get("/api/v1/reports/excel")
        assert resp.status_code in (401, 403)

    def test_pdf_without_token(self, persistent_auth_client):
        resp = persistent_auth_client.get("/api/v1/reports/pdf")
        assert resp.status_code in (401, 403)

    def test_csv_with_token(self, persistent_auth_client):
        persistent_auth_client.post("/api/v1/auth/register", json={
            "email": "report@example.com",
            "username": "reportuser",
            "password": "password123",
        })
        login_resp = persistent_auth_client.post("/api/v1/auth/login", json={
            "username": "reportuser",
            "password": "password123",
        })
        token = login_resp.json()["access_token"]

        resp = persistent_auth_client.get(
            "/api/v1/reports/csv",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


# ===========================================
# 공개 API 접근 테스트 (인증 불필요 확인)
# ===========================================

class TestPublicAPIs:
    def test_dashboard_no_auth(self, client):
        resp = client.get("/api/v1/risks/dashboard")
        assert resp.status_code == 200

    def test_airports_no_auth(self, client):
        resp = client.get("/api/v1/airports")
        assert resp.status_code == 200

    def test_weather_no_auth(self, client):
        resp = client.get("/api/v1/weather")
        assert resp.status_code == 200
