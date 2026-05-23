"""
테스트 공통 픽스처

모든 테스트는 이 conftest.py의 픽스처를 통해 DB에 접근합니다.
실제 PostgreSQL 대신 SQLite in-memory DB를 사용하므로
docker-compose 없이 로컬에서 바로 실행 가능합니다.

실행 방법 (project/backend/ 디렉토리에서):
    pip install -r requirements.txt -r requirements-test.txt
    pytest tests/ -v
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app

# SQLite in-memory DB (테스트 전용)
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """
    각 테스트 함수마다 독립된 DB 세션을 제공합니다.
    테스트 후 롤백하여 테스트 간 데이터가 섞이지 않습니다.
    """
    Base.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    Base.metadata.drop_all(bind=engine)


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
