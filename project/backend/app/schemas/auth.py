from typing import Literal
from pydantic import BaseModel, field_validator

Gender = Literal["male", "female"]


class RegisterRequest(BaseModel):
    username: str
    password: str
    gender: Gender
    email: str

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

    @field_validator("email")
    @classmethod
    def email_must_be_hanyang(cls, v: str) -> str:
        if not v.lower().endswith("@hanyang.ac.kr"):
            raise ValueError("한양대학교 이메일(@hanyang.ac.kr)만 가능합니다")
        return v.lower()


class RegisterResponse(BaseModel):
    message: str
    email: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    gender: str
    role: str