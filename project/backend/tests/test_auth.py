"""
회원가입/로그인/이메일 인증 엔드포인트 테스트
이메일 발송은 monkeypatch로 mock 처리
"""
import pytest


VALID_EMAIL = "student@hanyang.ac.kr"
VALID_PAYLOAD = {
    "username": "testuser",
    "password": "pass1234",
    "gender": "male",
    "email": VALID_EMAIL,
}


@pytest.fixture(autouse=True)
def mock_send_email(monkeypatch):
    monkeypatch.setattr("app.services.auth_service.send_verification_email", lambda email, code: None)


def _register(client, payload=None):
    return client.post("/auth/register", json=payload or VALID_PAYLOAD)


def _get_code(db, email=VALID_EMAIL):
    from app.models.email_verification import EmailVerification
    v = db.query(EmailVerification).filter(EmailVerification.email == email).first()
    return v.code if v else None


def test_register_success(client, db):
    res = _register(client)
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == VALID_EMAIL
    assert "인증 코드" in data["message"]


def test_register_invalid_email_domain(client):
    payload = {**VALID_PAYLOAD, "email": "student@gmail.com"}
    res = _register(client, payload)
    assert res.status_code == 422


def test_register_duplicate_username(client):
    _register(client)
    res = _register(client)
    assert res.status_code == 400


def test_register_duplicate_email(client):
    _register(client)
    payload = {**VALID_PAYLOAD, "username": "otheruser"}
    res = _register(client, payload)
    assert res.status_code == 400


def test_register_short_username(client):
    payload = {**VALID_PAYLOAD, "username": "a"}
    res = _register(client, payload)
    assert res.status_code == 422


def test_register_short_password(client):
    payload = {**VALID_PAYLOAD, "password": "abc"}
    res = _register(client, payload)
    assert res.status_code == 422


def test_verify_email_success(client, db):
    _register(client)
    code = _get_code(db)
    res = client.post("/auth/verify-email", json={"email": VALID_EMAIL, "code": code})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["username"] == "testuser"


def test_verify_email_wrong_code(client, db):
    _register(client)
    res = client.post("/auth/verify-email", json={"email": VALID_EMAIL, "code": "000000"})
    assert res.status_code == 400


def test_verify_email_not_found(client):
    res = client.post("/auth/verify-email", json={"email": "nobody@hanyang.ac.kr", "code": "123456"})
    assert res.status_code == 400


def test_login_unverified(client, db):
    _register(client)
    res = client.post("/auth/login", json={"username": "testuser", "password": "pass1234"})
    assert res.status_code == 403


def test_login_success(client, db):
    _register(client)
    code = _get_code(db)
    client.post("/auth/verify-email", json={"email": VALID_EMAIL, "code": code})
    res = client.post("/auth/login", json={"username": "testuser", "password": "pass1234"})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_login_wrong_password(client, db):
    _register(client)
    code = _get_code(db)
    client.post("/auth/verify-email", json={"email": VALID_EMAIL, "code": code})
    res = client.post("/auth/login", json={"username": "testuser", "password": "wrongpass"})
    assert res.status_code == 401


def test_login_nonexistent_user(client):
    res = client.post("/auth/login", json={"username": "ghost", "password": "pass1234"})
    assert res.status_code == 401
