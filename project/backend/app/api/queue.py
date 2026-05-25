from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.ws_manager import manager
from app.models.user import User
from app.repositories import queue_repo
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