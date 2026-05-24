"""
Mode B 소프트 예약 테스트 (POST /machines/request)
"""
from tests.conftest import register_and_login
from app.models.machine import Machine


def _set_available_count(db, gender: str, target: int):
    """남기고 싶은 수만큼만 available, 나머지 in_use."""
    machines = db.query(Machine).filter(
        (Machine.gender_restriction == gender) | (Machine.gender_restriction == None)  # noqa: E711
    ).all()
    for i, m in enumerate(machines):
        m.status = "available" if i < target else "in_use"
    db.commit()


def test_request_machine_mode_b(seeded_client, db):
    """Mode B (1~3대): 요청 시 세탁기 배정 + reserved_until 반환"""
    _set_available_count(db, "male", 2)
    token = register_and_login(seeded_client, "user_b", "male")

    response = seeded_client.post("/machines/request", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "assigned_machine" in data
    assert data["assigned_machine"]["floor"] is not None
    assert "reserved_until" in data


def test_request_machine_mode_a_rejected(seeded_client, db):
    """Mode A (4대↑): 요청 거부"""
    _set_available_count(db, "female", 5)
    token = register_and_login(seeded_client, "user_a", "female")

    response = seeded_client.post("/machines/request", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_request_machine_mode_c_rejected(seeded_client, db):
    """Mode C (0대): 요청 거부"""
    _set_available_count(db, "male", 0)
    token = register_and_login(seeded_client, "user_c", "male")

    response = seeded_client.post("/machines/request", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_request_requires_auth(seeded_client):
    response = seeded_client.post("/machines/request")
    assert response.status_code == 403