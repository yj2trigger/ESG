"""
테스트 공통 픽스처

모든 테스트는 이 conftest.py의 픽스처를 통해 DB에 접근합니다.
실제 PostgreSQL 대신 SQLite in-memory DB를 사용하므로
docker-compose 없이 로컬에서 바로 실행 가능합니다.

실행 방법 (project/backend/ 디렉토리에서):
    pip install -r requirements.txt -r requirements-test.txt
    pytest tests/ -v
"""

import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# Disable rate limiting before app modules are imported
from app.core.limiter import limiter
limiter.limit = lambda *args, **kwargs: lambda func: func

# Disable email sending in all tests
import app.services.auth_service as _auth_service
_auth_service.send_verification_email = lambda email, code: None

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
from app.repositories import machine_repo

# SQLite in-memory DB (테스트 전용)
TEST_DATABASE_URL = "sqlite:///./test.db"

test_engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db():
    """
    각 테스트 함수마다 독립된 DB 세션을 제공합니다.
    테스트 시작 시 테이블 생성, 종료 시 드롭하여 테스트 간 완전히 격리됩니다.
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db):
    """
    FastAPI TestClient — DB 세션을 테스트용으로 교체합니다.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seeded_client(db):
    """TestClient with seeded machine data."""
    machine_repo.seed(db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register_and_login(client, username: str = "user1", gender: str = "male") -> str:
    """Helper: register + verify email + return Bearer token."""
    email = f"{username}@hanyang.ac.kr"
    client.post("/auth/register", json={"username": username, "password": "pass1234", "gender": gender, "email": email})

    from app.models.email_verification import EmailVerification
    db_session = TestingSessionLocal()
    try:
        v = db_session.query(EmailVerification).filter(EmailVerification.email == email).first()
        code = v.code if v else "000000"
    finally:
        db_session.close()

    res = client.post("/auth/verify-email", json={"email": email, "code": code})
    return res.json()["access_token"]
