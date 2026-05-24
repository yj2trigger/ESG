from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.ws_manager import manager
from app.models.user import User
from app.schemas.queue import QueueJoinResponse, QueueLeaveResponse
from app.services import machine_service, queue_service

router = APIRouter(prefix="/queue", tags=["queue"])


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
    return result