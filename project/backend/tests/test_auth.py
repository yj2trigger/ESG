"""
회원가입/로그인 엔드포인트 테스트
"""


def test_register_success(client):
    response = client.post("/auth/register", json={
        "username": "testuser",
        "password": "pass1234",
        "gender": "male",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == "testuser"
    assert data["gender"] == "male"
    assert data["role"] == "user"


def test_register_duplicate_username(client):
    payload = {"username": "dup", "password": "pass1234", "gender": "female"}
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400


def test_register_short_username(client):
    response = client.post("/auth/register", json={
        "username": "a",
        "password": "pass1234",
        "gender": "male",
    })
    assert response.status_code == 422


def test_register_short_password(client):
    response = client.post("/auth/register", json={
        "username": "validuser",
        "password": "abc",
        "gender": "female",
    })
    assert response.status_code == 422


def test_login_success(client):
    client.post("/auth/register", json={"username": "loginuser", "password": "pass1234", "gender": "male"})
    response = client.post("/auth/login", json={"username": "loginuser", "password": "pass1234"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "loginuser2", "password": "pass1234", "gender": "female"})
    response = client.post("/auth/login", json={"username": "loginuser2", "password": "wrongpass"})
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    response = client.post("/auth/login", json={"username": "ghost", "password": "pass1234"})
    assert response.status_code == 401