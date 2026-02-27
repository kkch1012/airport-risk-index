"""
인증 관련 Pydantic 스키마
"""

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('password')
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError('비밀번호에 숫자가 포함되어야 합니다')
        if not any(c.isalpha() for c in v):
            raise ValueError('비밀번호에 영문자가 포함되어야 합니다')
        return v


class UserLoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    is_active: bool

    model_config = {"from_attributes": True}
