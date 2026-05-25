from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_admin_user
from app.core.ws_manager import manager
from app.models.user import User
from app.repositories import machine_repo
from app.schemas.machine import MachineAdminItem, MachineStatusUpdate
from app.services.machine_service import get_dashboard

router = APIRouter(prefix="/admin", tags=["admin"])


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
    updated = machine_repo.set_status(db, machine, body.status)

    gender = machine.gender_restriction
    for g in (["male", "female"] if gender is None else [gender]):
        dashboard = get_dashboard(db, g)
        background_tasks.add_task(
            manager.broadcast, g, {"type": "machines_updated", **dashboard.model_dump()}
        )

    return updated
