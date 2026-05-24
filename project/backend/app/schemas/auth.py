from typing import Literal
from pydantic import BaseModel, field_validator

Gender = Literal["male", "female"]


class RegisterRequest(BaseModel):
    username: str
    password: str
    gender: Gender

    @field_validator("username")
    @classmethod
    def username_min_length(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("사용자명은 2자 이상이어야 합니다")
        return v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("비밀번호는 4자 이상이어야 합니다")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    gender: str
    role: str