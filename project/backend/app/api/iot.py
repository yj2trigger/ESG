from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal, get_db
from app.repositories import machine_repo, machine_status_log_repo

router = APIRouter(prefix="/iot", tags=["iot"])


class MachineSignal(BaseModel):
    is_running: bool


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
    """소프트 예약자에게 세탁기 작동 시작 알림 전송."""
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

    previous_status = machine.status

    # 고장 상태는 IoT 신호로 자동 전환 불가 — 관리자 수동 복구만 가능
    if previous_status == "broken":
        return {"machine_id": machine_id, "status": "broken", "changed": False}

    # soft_reserved 보호:
    # - 전력 낙음(is_running=False): 예약자가 아직 세탁기를 켜지 않음 → 예약 유지 (만료 타이머에 위임)
    # - 전력 높음(is_running=True): 예약자가 세탁기를 가동 → in_use로 전환 + 시작 알림
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

    gender = machine.gender_restriction
    genders = ["male", "female"] if gender is None else [gender]

    if new_status == "available":
        for g in genders:
            background_tasks.add_task(_handle_available, g)
    else:  # in_use
        if reserved_user_id:
            background_tasks.add_task(
                _handle_machine_started, reserved_user_id, genders[0], machine_floor, machine_number
            )
        for g in genders:
            background_tasks.add_task(_handle_in_use, g)

    return {"machine_id": machine_id, "status": new_status, "changed": True}
