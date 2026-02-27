"""
인증 API 엔드포인트 (회원가입, 로그인, 내 정보)
"""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth_dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_by_email,
    get_user_by_username,
)

router = APIRouter()

# --- Rate Limiting ---
_login_attempts: dict[str, list[float]] = defaultdict(list)
_register_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_WINDOW = 900  # 15분
_MAX_LOGIN = 10
_MAX_REGISTER = 5


def _reset_rate_limits():
    """테스트용: rate limit 저장소 초기화"""
    _login_attempts.clear()
    _register_attempts.clear()


def _check_rate_limit(store: dict, key: str, max_attempts: int) -> bool:
    now = time.time()
    store[key] = [t for t in store[key] if now - t < _RATE_WINDOW]
    if len(store[key]) >= max_attempts:
        return False
    store[key].append(now)
    return True


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(req: UserRegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """회원가입"""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(_register_attempts, client_ip, _MAX_REGISTER):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")

    if await get_user_by_email(db, req.email) or await get_user_by_username(db, req.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="등록에 실패했습니다. 다른 정보로 시도해주세요.")

    user = await create_user(db, req.email, req.username, req.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """로그인 (JWT 토큰 발급)"""
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(_login_attempts, client_ip, _MAX_LOGIN):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="로그인 시도가 너무 많습니다. 15분 후 다시 시도해주세요.")

    user = await authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="잘못된 사용자명 또는 비밀번호입니다.")

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """내 정보 조회"""
    return current_user
