"""
인증 API 엔드포인트 (회원가입, 로그인, 내 정보)
"""

from fastapi import APIRouter, Depends, HTTPException, status
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


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(req: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """회원가입"""
    if await get_user_by_email(db, req.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 이메일입니다.")
    if await get_user_by_username(db, req.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 사용자명입니다.")

    user = await create_user(db, req.email, req.username, req.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(req: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """로그인 (JWT 토큰 발급)"""
    user = await authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="잘못된 사용자명 또는 비밀번호입니다.")

    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """내 정보 조회"""
    return current_user
