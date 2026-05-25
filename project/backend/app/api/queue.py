from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.dependencies import get_current_user
from app.core.ws_manager import manager
from app.models.user import User
from app.repositories import machine_repo, queue_repo
from app.schemas.machine import MachineDetail, MachineRequestResponse
from app.schemas.queue import QueueJoinResponse, QueueLeaveResponse, QueueStatusResponse
from app.services import machine_service, queue_service
from app.api.ws import broadcast_queue_positions

router = APIRouter(prefix="/queue", tags=["queue"])


@router.get("/status", response_model=QueueStatusResponse)
def get_queue_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = queue_repo.get_waiting_entry(db, current_user.id)
    if not entry:
        return QueueStatusResponse(in_queue=False)
    position = queue_repo.get_position(db, current_user.id, current_user.gender)
    total = queue_repo.count_waiting(db, current_user.gender)
    return QueueStatusResponse(in_queue=True, queue_position=position, total=total)


@router.post("/join", response_model=QueueJoinResponse)
async def join_queue(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = queue_service.join_queue(db, current_user)
    dashboard = machine_service.get_dashboard(db, current_user.gender)
    background_tasks.add_task(
        manager.broadcast,
        current_user.gender,
        {"type": "machines_updated", **dashboard.model_dump()},
    )
    return result


@router.delete("/leave", response_model=QueueLeaveResponse)
async def leave_queue(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = queue_service.leave_queue(db, current_user)
    dashboard = machine_service.get_dashboard(db, current_user.gender)
    background_tasks.add_task(
        manager.broadcast,
        current_user.gender,
        {"type": "machines_updated", **dashboard.model_dump()},
    )
    await broadcast_queue_positions(db, current_user.gender)
    return result


@router.post("/accept", response_model=MachineRequestResponse)
async def accept_queue_offer(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = queue_repo.get_notified_entry(db, current_user.id)
    if not entry:
        raise HTTPException(status_code=400, detail="수락할 수 있는 배정이 없습니다")

    machine = machine_repo.get_active_reserve(db, current_user.id)
    if not machine:
        # Offer timed out — clean up stale notified entry
        queue_repo.leave(db, current_user.id)
        raise HTTPException(status_code=400, detail="배정 시간이 초과되었습니다")

    # Extend soft reservation to 10 minutes from now
    machine_repo.soft_reserve(db, machine, current_user.id, duration_minutes=10)
    queue_repo.leave(db, current_user.id)

    gender = current_user.gender

    async def _broadcast() -> None:
        _db = SessionLocal()
        try:
            dashboard = machine_service.get_dashboard(_db, gender)
            await manager.broadcast(gender, {"type": "machines_updated", **dashboard.model_dump()})
            await broadcast_queue_positions(_db, gender)
        finally:
            _db.close()

    background_tasks.add_task(_broadcast)

    return MachineRequestResponse(
        assigned_machine=MachineDetail(
            id=machine.id,
            floor=machine.floor,
            machine_number=machine.machine_number,
        ),
        reserved_until=machine.reserved_until,
    )
