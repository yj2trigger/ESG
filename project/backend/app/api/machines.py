from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.ws_manager import manager
from app.models.user import User
from app.schemas.machine import MachineRequestResponse, MachinesResponse
from app.services import machine_service

router = APIRouter(prefix="/machines", tags=["machines"])


@router.get("", response_model=MachinesResponse)
def get_machines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return machine_service.get_dashboard(db, current_user.gender)


@router.post("/request", response_model=MachineRequestResponse)
async def request_machine(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = machine_service.request_machine(db, current_user)
    dashboard = machine_service.get_dashboard(db, current_user.gender)
    background_tasks.add_task(
        manager.broadcast,
        current_user.gender,
        {"type": "machines_updated", **dashboard.model_dump()},
    )
    return result