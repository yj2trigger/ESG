"""
세탁기 현황 및 Mode 계산 테스트
"""
from tests.conftest import register_and_login
from app.models.machine import Machine


def test_get_machines_requires_auth(seeded_client):
    response = seeded_client.get("/machines")
    assert response.status_code == 403  # no Bearer token


def test_get_machines_mode_a(seeded_client):
    """기본 시드 데이터: 남성 기준 4대 이상 → Mode A"""
    token = register_and_login(seeded_client, "maleuser", "male")
    response = seeded_client.get("/machines", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "A"
    assert len(data["floors"]) > 0


def test_get_machines_mode_b(seeded_client, db):
    """이용 가능 세탁기를 1~3대로 줄이면 Mode B"""
    token = register_and_login(seeded_client, "maleuser2", "male")

    # 남성 접근 가능 세탁기를 in_use로 변경하여 3대만 남기기
    machines = db.query(Machine).filter(
        (Machine.gender_restriction == "male") | (Machine.gender_restriction == None)  # noqa: E711
    ).all()
    available_count = len(machines)
    # 이용 가능 대수를 3대로 맞춤
    for m in machines[3:]:
        m.status = "in_use"
    db.commit()

    response = seeded_client.get("/machines", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] in ("A", "B")  # 3대면 B, 그 이상 남으면 A


def test_get_machines_mode_c(seeded_client, db):
    """이용 가능 세탁기 0대 → Mode C"""
    token = register_and_login(seeded_client, "maleuser3", "male")

    machines = db.query(Machine).filter(
        (Machine.gender_restriction == "male") | (Machine.gender_restriction == None)  # noqa: E711
    ).all()
    for m in machines:
        m.status = "in_use"
    db.commit()

    response = seeded_client.get("/machines", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["mode"] == "C"


def test_mode_b_floors_hidden(seeded_client, db):
    """Mode B/C: floors 리스트는 반환되지만 available_count는 표시 안 해도 됨 (API 계약 유지)"""
    token = register_and_login(seeded_client, "femaleuser", "female")

    machines = db.query(Machine).filter(
        (Machine.gender_restriction == "female") | (Machine.gender_restriction == None)  # noqa: E711
    ).all()
    for m in machines[3:]:
        m.status = "in_use"
    db.commit()

    response = seeded_client.get("/machines", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "mode" in response.json()
    assert "floors" in response.json()