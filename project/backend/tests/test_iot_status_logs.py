from app.config import settings
from app.models.machine import Machine, MachineStatusLog


def test_iot_signal_stores_status_log_on_change(seeded_client, db):
    settings.iot_device_key = "test-device-key"
    machine = db.query(Machine).first()

    response = seeded_client.post(
        f"/iot/machines/{machine.id}/status",
        json={"is_running": True},
        headers={"X-Device-Key": "test-device-key"},
    )

    assert response.status_code == 200
    assert response.json()["changed"] is True

    log = db.query(MachineStatusLog).filter(MachineStatusLog.machine_id == machine.id).one()
    assert log.previous_status == "available"
    assert log.status == "in_use"
    assert log.source == "iot"
    assert log.is_running is True
    assert log.changed is True
    assert log.recorded_at is not None


def test_iot_signal_stores_status_log_without_status_change(seeded_client, db):
    settings.iot_device_key = "test-device-key"
    machine = db.query(Machine).first()
    machine.status = "in_use"
    db.commit()

    response = seeded_client.post(
        f"/iot/machines/{machine.id}/status",
        json={"is_running": True},
        headers={"X-Device-Key": "test-device-key"},
    )

    assert response.status_code == 200
    assert response.json()["changed"] is False

    log = db.query(MachineStatusLog).filter(MachineStatusLog.machine_id == machine.id).one()
    assert log.previous_status == "in_use"
    assert log.status == "in_use"
    assert log.source == "iot"
    assert log.is_running is True
    assert log.changed is False