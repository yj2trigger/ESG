from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.dependencies import get_admin_user
from app.core.ws_manager import manager
from app.models.user import User
from app.repositories import machine_repo, machine_status_log_repo
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
    _: User = Depends(get_admin_user),
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