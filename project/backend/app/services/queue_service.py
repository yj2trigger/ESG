from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import queue_repo
from app.schemas.queue import QueueJoinResponse, QueueLeaveResponse
from app.services.machine_service import get_current_mode


def join_queue(db: Session, user: User) -> QueueJoinResponse:
    mode = get_current_mode(db, user.gender)
    if mode != "C":
        raise HTTPException(status_code=400, detail=f"현재 Mode {mode}입니다. Mode C에서만 대기열 등록이 가능합니다")

    entry = queue_repo.join(db, user.id, user.gender)
    position = queue_repo.get_position(db, entry.user_id, user.gender)
    return QueueJoinResponse(queue_position=position, message="대기열에 등록되었습니다")


def leave_queue(db: Session, user: User) -> QueueLeaveResponse:
    removed = queue_repo.leave(db, user.id)
    if not removed:
        raise HTTPException(status_code=404, detail="대기열에 등록되어 있지 않습니다")
    return QueueLeaveResponse(message="대기열에서 취소되었습니다")