import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status  # noqa: F401
from sqlalchemy.orm import Session

from app.core.email import send_verification_email
from app.core.security import create_access_token, hash_password, verify_password
from app.models.email_verification import EmailVerification
from app.repositories import user_repo


def register(db: Session, username: str, password: str, gender: str, email: str) -> dict:
    if user_repo.get_by_username(db, username):
        raise HTTPException(status_code=400, detail="이미 존재하는 사용자명입니다")

    existing = db.query(user_repo.User).filter(user_repo.User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다")

    hashed = hash_password(password)
    user = user_repo.create(db, username, hashed, gender, email)

    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    db.query(EmailVerification).filter(EmailVerification.email == email).delete()
    verification = EmailVerification(email=email, code=code, expires_at=expires_at)
    db.add(verification)
    db.commit()

    send_verification_email(email, code)

    return {"message": "인증 코드를 이메일로 발송했습니다", "email": email}


def verify_email(db: Session, email: str, code: str) -> dict:
    verification = (
        db.query(EmailVerification)
        .filter(EmailVerification.email == email)
        .first()
    )
    if not verification:
        raise HTTPException(status_code=400, detail="인증 요청을 찾을 수 없습니다")
    if verification.code != code:
        raise HTTPException(status_code=400, detail="인증 코드가 올바르지 않습니다")
    exp = verification.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="인증 코드가 만료됐습니다. 다시 회원가입해주세요")

    user = db.query(user_repo.User).filter(user_repo.User.email == email).first()
    if not user:
        raise HTTPException(status_code=400, detail="사용자를 찾을 수 없습니다")

    user.is_verified = True
    db.delete(verification)
    db.commit()

    token = create_access_token({"sub": user.username, "gender": user.gender, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "gender": user.gender, "role": user.role}


def change_password(db: Session, user, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="현재 비밀번호가 틀렸습니다")
    user.password_hash = hash_password(new_password)
    db.commit()


def change_username(db: Session, user, current_password: str, new_username: str) -> dict:
    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="현재 비밀번호가 틀렸습니다")
    if user_repo.get_by_username(db, new_username):
        raise HTTPException(status_code=400, detail="이미 사용 중인 사용자명입니다")
    user.username = new_username
    db.commit()
    token = create_access_token({"sub": user.username, "gender": user.gender, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "gender": user.gender, "role": user.role}


def login(db: Session, username: str, password: str) -> dict:
    user = user_repo.get_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="아이디 또는 비밀번호가 틀렸습니다")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="이메일 인증이 필요합니다")
    token = create_access_token({"sub": user.username, "gender": user.gender, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "gender": user.gender, "role": user.role}
