"""
IoT 엔드포인트 상태 전환 테스트
"""

from app.models.machine import Machine

IOT_KEY = "test-iot-key"


def _h():
    return {"x-device-key": IOT_KEY}


def test_iot_available_to_in_use(seeded_client, db):
    machine = db.query(Machine).filter(Machine.status == "available").first()
    assert machine is not None
    resp = seeded_client.post(
        f"/iot/machines/{machine.id}/status",
        json={"is_running": True, "power_w": 56.0},
        headers=_h(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_use"
    db.refresh(machine)
    assert machine.status == "in_use"


def test_iot_in_use_to_available(seeded_client, db):
    machine = db.query(Machine).filter(Machine.status == "available").first()
    machine.status = "in_use"
    db.commit()
    resp = seeded_client.post(
        f"/iot/machines/{machine.id}/status",
        json={"is_running": False, "power_w": 2.0},
        headers=_h(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "available"
    db.refresh(machine)
    assert machine.status == "available"


def test_iot_broken_not_changed(seeded_client, db):
    machine = db.query(Machine).filter(Machine.status == "available").first()
    machine.status = "broken"
    db.commit()
    resp = seeded_client.post(
        f"/iot/machines/{machine.id}/status",
        json={"is_running": True, "power_w": 56.0},
        headers=_h(),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "broken"
    assert resp.json()["changed"] is False
    db.refresh(machine)
    assert machine.status == "broken"


def test_iot_power_log_saved(seeded_client, db):
    from app.models.machine import MachinePowerLog
    machine = db.query(Machine).filter(Machine.status == "available").first()
    seeded_client.post(
        f"/iot/machines/{machine.id}/status",
        json={"is_running": True, "power_w": 42.5},
        headers=_h(),
    )
    log = db.query(MachinePowerLog).filter(MachinePowerLog.machine_id == machine.id).first()
    assert log is not None
    assert abs(log.power_w - 42.5) < 0.01


def test_iot_no_auth(seeded_client, db):
    machine = db.query(Machine).filter(Machine.status == "available").first()
    resp = seeded_client.post(
        f"/iot/machines/{machine.id}/status",
        json={"is_running": True},
    )
    assert resp.status_code == 422
