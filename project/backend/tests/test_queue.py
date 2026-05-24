"""
Mode C 대기열 테스트 (POST /queue/join, DELETE /queue/leave)
"""
from tests.conftest import register_and_login
from app.models.machine import Machine


def _set_all_in_use(db, gender: str):
    machines = db.query(Machine).filter(
        (Machine.gender_restriction == gender) | (Machine.gender_restriction == None)  # noqa: E711
    ).all()
    for m in machines:
        m.status = "in_use"
    db.commit()


def test_join_queue_mode_c(seeded_client, db):
    _set_all_in_use(db, "male")
    token = register_and_login(seeded_client, "waiter1", "male")

    response = seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["queue_position"] == 1
    assert "대기열" in data["message"]


def test_join_queue_position_order(seeded_client, db):
    _set_all_in_use(db, "female")
    token1 = register_and_login(seeded_client, "waiter_f1", "female")
    token2 = register_and_login(seeded_client, "waiter_f2", "female")

    r1 = seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token1}"})
    r2 = seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token2}"})
    assert r1.json()["queue_position"] == 1
    assert r2.json()["queue_position"] == 2


def test_join_queue_duplicate_rejected(seeded_client, db):
    _set_all_in_use(db, "male")
    token = register_and_login(seeded_client, "dup_waiter", "male")

    seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})
    response = seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_join_queue_mode_b_rejected(seeded_client, db):
    """Mode B (1~3대): 대기열 등록 불가"""
    machines = db.query(Machine).filter(
        (Machine.gender_restriction == "male") | (Machine.gender_restriction == None)  # noqa: E711
    ).all()
    for i, m in enumerate(machines):
        m.status = "available" if i < 2 else "in_use"
    db.commit()

    token = register_and_login(seeded_client, "mode_b_user", "male")
    response = seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_leave_queue(seeded_client, db):
    _set_all_in_use(db, "male")
    token = register_and_login(seeded_client, "leaver", "male")

    seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})
    response = seeded_client.delete("/queue/leave", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "취소" in response.json()["message"]


def test_leave_queue_not_in_queue(seeded_client):
    token = register_and_login(seeded_client, "notinqueue", "female")
    response = seeded_client.delete("/queue/leave", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404