from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.queue_entry import QueueEntry


def get_waiting_entry(db: Session, user_id: int) -> QueueEntry | None:
    return (
        db.query(QueueEntry)
        .filter(QueueEntry.user_id == user_id, QueueEntry.status == "waiting")
        .first()
    )


def join(db: Session, user_id: int, gender: str) -> QueueEntry:
    if get_waiting_entry(db, user_id):
        raise HTTPException(status_code=400, detail="이미 대기열에 등록되어 있습니다")
    entry = QueueEntry(user_id=user_id, gender=gender)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_position(db: Session, user_id: int, gender: str) -> int:
    entries = (
        db.query(QueueEntry)
        .filter(QueueEntry.gender == gender, QueueEntry.status == "waiting")
        .order_by(QueueEntry.created_at)
        .all()
    )
    for i, e in enumerate(entries):
        if e.user_id == user_id:
            return i + 1
    return -1


def leave(db: Session, user_id: int) -> bool:
    entry = get_waiting_entry(db, user_id)
    if not entry:
        return False
    db.delete(entry)
    db.commit()
    return True


def get_next_waiter(db: Session, gender: str) -> QueueEntry | None:
    return (
        db.query(QueueEntry)
        .filter(QueueEntry.gender == gender, QueueEntry.status == "waiting")
        .order_by(QueueEntry.created_at)
        .first()
    )