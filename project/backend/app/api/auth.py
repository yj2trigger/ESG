from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.limiter import limiter
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse, VerifyEmailRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest, db: Session = Depends(get_db)):
    return auth_service.register(db, req.username, req.password, req.gender, req.email)


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    return auth_service.verify_email(db, req.email, req.code)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login(db, req.username, req.password)
