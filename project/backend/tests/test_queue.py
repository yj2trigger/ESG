"""
Mode C 대기열 테스트 (POST /queue/join, DELETE /queue/leave, GET /queue/status, POST /queue/accept)
"""
from datetime import datetime, timedelta, timezone

from tests.conftest import register_and_login
from app.models.machine import Machine
from app.models.queue_entry import QueueEntry


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


# ── GET /queue/status ─────────────────────────────────────────

def test_queue_status_not_in_queue(seeded_client):
    token = register_and_login(seeded_client, "status_none", "male")
    res = seeded_client.get("/queue/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["in_queue"] is False
    assert data["is_notified"] is False


def test_queue_status_waiting(seeded_client, db):
    _set_all_in_use(db, "male")
    token = register_and_login(seeded_client, "status_wait", "male")
    seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})

    res = seeded_client.get("/queue/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["in_queue"] is True
    assert data["is_notified"] is False
    assert data["queue_position"] == 1
    assert data["total"] == 1


def test_queue_status_notified(seeded_client, db):
    """notified 상태 → is_notified=True, accept_until 반환."""
    _set_all_in_use(db, "male")
    token = register_and_login(seeded_client, "status_notified", "male")
    seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})

    # 대기열 entry를 직접 notified 상태로 전환
    from app.models.user import User
    user = db.query(User).filter(User.username == "status_notified").first()
    entry = db.query(QueueEntry).filter(QueueEntry.user_id == user.id).first()
    now = datetime.now(timezone.utc)
    entry.status = "notified"
    entry.notified_at = now
    entry.expires_at = now + timedelta(minutes=5)
    db.commit()

    res = seeded_client.get("/queue/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["in_queue"] is True
    assert data["is_notified"] is True
    assert data["accept_until"] is not None
    assert data["queue_position"] is None


# ── POST /queue/accept ────────────────────────────────────────

def _setup_notified_offer(db, user_id: int, gender: str):
    """테스트용: 세탁기 soft_reserve + 대기열 notified 상태 직접 세팅."""
    machine = db.query(Machine).filter(
        (Machine.gender_restriction == gender) | (Machine.gender_restriction == None)  # noqa: E711
    ).first()
    now = datetime.now(timezone.utc)
    machine.status = "soft_reserved"
    machine.reserved_by_user_id = user_id
    machine.reserved_until = now + timedelta(minutes=5)

    entry = QueueEntry(
        user_id=user_id,
        gender=gender,
        status="notified",
        notified_at=now,
        expires_at=now + timedelta(minutes=5),
    )
    db.add(entry)
    db.commit()
    return machine


def test_accept_queue_offer_success(seeded_client, db):
    token = register_and_login(seeded_client, "accepter", "male")

    from app.models.user import User
    user = db.query(User).filter(User.username == "accepter").first()
    _setup_notified_offer(db, user.id, "male")

    res = seeded_client.post("/queue/accept", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "assigned_machine" in data
    assert data["assigned_machine"]["floor"] is not None
    assert "reserved_until" in data
    # 대기열 entry 삭제 확인
    assert db.query(QueueEntry).filter(QueueEntry.user_id == user.id).first() is None


def test_accept_queue_offer_no_offer(seeded_client):
    """notified 대기열 항목 없이 accept → 400."""
    token = register_and_login(seeded_client, "no_offer", "male")
    res = seeded_client.post("/queue/accept", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400


def test_accept_queue_offer_expired(seeded_client, db):
    """5분 만료된 soft_reserve → accept 시 400."""
    token = register_and_login(seeded_client, "expired_accepter", "male")

    from app.models.user import User
    user = db.query(User).filter(User.username == "expired_accepter").first()

    # notified entry는 있지만 machine reserved_until은 이미 지난 시각
    machine = db.query(Machine).filter(
        (Machine.gender_restriction == "male") | (Machine.gender_restriction == None)  # noqa: E711
    ).first()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    machine.status = "soft_reserved"
    machine.reserved_by_user_id = user.id
    machine.reserved_until = past

    now = datetime.now(timezone.utc)
    entry = QueueEntry(
        user_id=user.id,
        gender="male",
        status="notified",
        notified_at=now - timedelta(minutes=6),
        expires_at=now - timedelta(minutes=1),
    )
    db.add(entry)
    db.commit()

    res = seeded_client.post("/queue/accept", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400


# ── soft 예약 중 대기열 등록 거부 ────────────────────────────

def test_join_queue_rejected_when_soft_reserved(seeded_client, db):
    """이미 소프트 예약이 있으면 대기열 등록 불가."""
    _set_all_in_use(db, "female")
    token = register_and_login(seeded_client, "reserved_waiter", "female")

    from app.models.user import User
    user = db.query(User).filter(User.username == "reserved_waiter").first()

    # 여성 접근 가능 세탁기 하나를 해당 사용자가 soft_reserved 중으로 세팅
    machine = db.query(Machine).filter(
        (Machine.gender_restriction == "female") | (Machine.gender_restriction == None)  # noqa: E711
    ).first()
    machine.status = "soft_reserved"
    machine.reserved_by_user_id = user.id
    machine.reserved_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    res = seeded_client.post("/queue/join", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 400
    assert "예약된 세탁기를 이용해주세요" in res.json()["detail"]