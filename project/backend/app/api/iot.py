from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal, get_db
from app.repositories import machine_repo

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
    from app.api.ws import broadcast_queue_positions
    from app.core.ws_manager import manager
    from app.services.machine_service import get_dashboard
    db = SessionLocal()
    try:
        dashboard = get_dashboard(db, gender)
        await manager.broadcast(gender, {"type": "machines_updated", **dashboard.model_dump()})
    finally:
        db.close()


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

    new_status = "in_use" if body.is_running else "available"

    if machine.status == new_status:
        return {"machine_id": machine_id, "status": new_status, "changed": False}

    machine_repo.set_status(db, machine, new_status)

    gender = machine.gender_restriction
    genders = ["male", "female"] if gender is None else [gender]

    if new_status == "available":
        for g in genders:
            background_tasks.add_task(_handle_available, g)
    else:
        for g in genders:
            background_tasks.add_task(_handle_in_use, g)

    return {"machine_id": machine_id, "status": new_status, "changed": True}
