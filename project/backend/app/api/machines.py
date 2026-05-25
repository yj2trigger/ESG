from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.core.ws_manager import manager
from app.models.user import User
from app.repositories import machine_repo
from app.schemas.machine import MachineDetail, MachineRequestResponse, MachinesResponse, MyReservationResponse
from app.services import machine_service

router = APIRouter(prefix="/machines", tags=["machines"])


@router.get("", response_model=MachinesResponse)
def get_machines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return machine_service.get_dashboard(db, current_user.gender)


@router.get("/my-reservation", response_model=MyReservationResponse)
def get_my_reservation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    machine = machine_repo.get_active_reserve(db, current_user.id)
    if not machine:
        return MyReservationResponse(active=False)
    return MyReservationResponse(
        active=True,
        assigned_machine=MachineDetail(
            id=machine.id,
            floor=machine.floor,
            machine_number=machine.machine_number,
        ),
        reserved_until=machine.reserved_until,
    )


@router.post("/request", response_model=MachineRequestResponse)
@limiter.limit("3/minute")
async def request_machine(
    request: Request,
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