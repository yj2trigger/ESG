from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.repositories import user_repo


def register(db: Session, username: str, password: str, gender: str) -> dict:
    if user_repo.get_by_username(db, username):
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명입니다")
    hashed = hash_password(password)
    user = user_repo.create(db, username, hashed, gender)
    token = create_access_token({"sub": user.username, "gender": user.gender, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "gender": user.gender, "role": user.role}


def login(db: Session, username: str, password: str) -> dict:
    user = user_repo.get_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 틀렸습니다")
    token = create_access_token({"sub": user.username, "gender": user.gender, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "gender": user.gender, "role": user.role}