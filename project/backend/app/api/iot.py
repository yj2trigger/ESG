import time as _time

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal, get_db
from app.repositories import machine_repo, machine_power_log_repo, machine_status_log_repo

router = APIRouter(prefix="/iot", tags=["iot"])


class MachineSignal(BaseModel):
    is_running: bool
    power_w: float | None = None


def _verify_device_key(x_device_key: str = Header(...)):
    if not settings.iot_device_key:
        raise HTTPException(status_code=503, detail="IoT 연동이 설정되지 않았습니다")
    if x_device_key != settings.iot_device_key:
        raise HTTPException(status_code=403, detail="인증 실패")


async def _handle_available(gender: str) -> None:
    from app.api.ws import _notify_queue_and_broadcast
    db = SessionLocal()
    try:
        await _notify_queue_and_broadcast(db, gender)
    finally:
        db.close()


async def _handle_in_use(gender: str) -> None:
    from app.core.ws_manager import manager
    from app.services.machine_service import get_dashboard
    db = SessionLocal()
    try:
        dashboard = get_dashboard(db, gender)
        await manager.broadcast(gender, {"type": "machines_updated", **dashboard.model_dump()})
    finally:
        db.close()


async def _handle_machine_started(user_id: int, gender: str, floor: int, machine_number: int) -> None:
    from app.core.ws_manager import manager
    await manager.send_to_user(
        user_id,
        gender,
        {
            "type": "machine_started",
            "machine": {"floor": floor, "machine_number": machine_number},
            "message": "세탁기 작동이 시작되었습니다",
        },
    )


async def _broadcast_poll_tick(genders: list[str]) -> None:
    """릴레이가 호출할 때마다 poll_tick 전송 — 사용자 카운트다운 동기화."""
    from app.core.ws_manager import manager
    interval = settings.relay_poll_sec
    now = int(_time.time())
    for gender in genders:
        await manager.broadcast(gender, {
            "type": "poll_tick",
            "next_interval_sec": interval,
            "fast_interval_sec": interval,
            "slow_interval_sec": interval,
            "priority_count": 0,
            "last_polled_at": now,
        })


@router.post("/machines/{machine_id}/status")
async def receive_machine_signal(
    machine_id: int,
    body: MachineSignal,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_device_key),
):
    machine = machine_repo.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="머신을 찾을 수 없습니다")

    if body.power_w is not None:
        machine_power_log_repo.create(db, machine_id, body.power_w)

    previous_status = machine.status
    gender = machine.gender_restriction
    genders = ["male", "female"] if gender is None else [gender]

    # 수신 즉시 poll_tick 브로드쾐스트 — 사용자 카운트다운 리셋
    background_tasks.add_task(_broadcast_poll_tick, genders)

    if previous_status == "broken":
        return {"machine_id": machine_id, "status": "broken", "changed": False}

    if previous_status == "soft_reserved":
        if not body.is_running:
            machine_status_log_repo.create(
                db, machine, previous_status, "iot",
                previous_status=previous_status, is_running=False, changed=False,
            )
            return {"machine_id": machine_id, "status": previous_status, "changed": False}
        new_status = "in_use"
    else:
        new_status = "in_use" if body.is_running else "available"

    changed = previous_status != new_status

    reserved_user_id = (
        machine.reserved_by_user_id
        if previous_status == "soft_reserved" and new_status == "in_use"
        else None
    )
    machine_floor = machine.floor
    machine_number = machine.machine_number

    if changed:
        machine_repo.set_status(db, machine, new_status)

    machine_status_log_repo.create(
        db, machine, new_status, "iot",
        previous_status=previous_status, is_running=body.is_running, changed=changed,
    )

    if not changed:
        return {"machine_id": machine_id, "status": new_status, "changed": False}

    if new_status == "available":
        for g in genders:
            background_tasks.add_task(_handle_available, g)
    else:
        if reserved_user_id:
            background_tasks.add_task(
                _handle_machine_started, reserved_user_id, genders[0], machine_floor, machine_number
            )
        for g in genders:
            background_tasks.add_task(_handle_in_use, g)

    return {"machine_id": machine_id, "status": new_status, "changed": True}
