from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal, get_db
from app.core.dependencies import get_admin_user
from app.core.ws_manager import manager
from app.models.user import User
from app.repositories import machine_power_log_repo, machine_repo, machine_status_log_repo
from app.schemas.machine import MachineAdminItem, MachineStatusUpdate
from app.services.machine_service import get_dashboard

router = APIRouter(prefix="/admin", tags=["admin"])


async def _notify_gender(gender: str) -> None:
    from app.api.ws import _notify_queue_and_broadcast
    db = SessionLocal()
    try:
        await _notify_queue_and_broadcast(db, gender)
    finally:
        db.close()


async def _broadcast_gender(gender: str) -> None:
    db = SessionLocal()
    try:
        dashboard = get_dashboard(db, gender)
        await manager.broadcast(gender, {"type": "machines_updated", **dashboard.model_dump()})
    finally:
        db.close()


@router.get("/machines", response_model=list[MachineAdminItem])
def list_machines(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    return machine_repo.get_all(db)


@router.patch("/machines/{machine_id}", response_model=MachineAdminItem)
async def update_machine_status(
    machine_id: int,
    body: MachineStatusUpdate,
    background_tasks: BackgroundTasks,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    machine = machine_repo.get_by_id(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="머신을 찾을 수 없습니다")

    previous_status = machine.status
    changed = previous_status != body.status
    updated = machine_repo.set_status(db, machine, body.status)
    machine_status_log_repo.create(
        db,
        machine,
        body.status,
        "admin",
        previous_status=previous_status,
        changed_by_user_id=admin_user.id,
        changed=changed,
    )

    gender = machine.gender_restriction
    genders = ["male", "female"] if gender is None else [gender]

    if body.status == "available":
        for g in genders:
            background_tasks.add_task(_notify_gender, g)
    else:
        for g in genders:
            background_tasks.add_task(_broadcast_gender, g)

    return updated


@router.get("/machines/{machine_id}/power-history")
def get_power_history(
    machine_id: int,
    hours: int = Query(default=24, ge=1, le=168),
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    logs = machine_power_log_repo.get_history(db, machine_id, hours=hours)
    return [{"timestamp": log.recorded_at.isoformat(), "power_w": log.power_w} for log in logs]


@router.get("/settings")
def get_settings(_: User = Depends(get_admin_user)):
    return {
        "power_threshold_w": settings.power_threshold_w,
        "stop_threshold_w": settings.stop_threshold_w,
    }
