"""
테스트 공통 픽스처
"""

import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["IOT_DEVICE_KEY"] = "test-iot-key"

from app.core.limiter import limiter
limiter.limit = lambda *args, **kwargs: lambda func: func

import app.services.auth_service as _auth_service
_auth_service.send_verification_email = lambda email, code: None

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.repositories import machine_repo

TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def reset_settings():
    """settings 뭬돌지기 — 테스트에서 settings 직접 변경해도 다음 테스트에 영향 없음."""
    original_iot_key = settings.iot_device_key
    yield
    settings.iot_device_key = original_iot_key


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db):
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
