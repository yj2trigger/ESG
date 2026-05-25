from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.queue_entry import QueueEntry


def get_entry(db: Session, user_id: int) -> QueueEntry | None:
    return db.query(QueueEntry).filter(QueueEntry.user_id == user_id).first()


def get_waiting_entry(db: Session, user_id: int) -> QueueEntry | None:
    return (
        db.query(QueueEntry)
        .filter(QueueEntry.user_id == user_id, QueueEntry.status == "waiting")
        .first()
    )


def get_notified_entry(db: Session, user_id: int) -> QueueEntry | None:
    return (
        db.query(QueueEntry)
        .filter(QueueEntry.user_id == user_id, QueueEntry.status == "notified")
        .first()
    )


def join(db: Session, user_id: int, gender: str) -> QueueEntry:
    if get_entry(db, user_id):
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
    entry = get_entry(db, user_id)
    if not entry:
        return False
    db.delete(entry)
    db.commit()
    return True


def set_notified(db: Session, entry: QueueEntry, accept_minutes: int = 5) -> QueueEntry:
    now = datetime.now(timezone.utc)
    entry.status = "notified"
    entry.notified_at = now
    entry.expires_at = now + timedelta(minutes=accept_minutes)
    db.commit()
    db.refresh(entry)
    return entry


def reset_expired_notifications(db: Session, gender: str) -> list[int]:
    """Move expired notified entries back to waiting (end of queue). Returns affected user_ids."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(QueueEntry)
        .filter(
            QueueEntry.gender == gender,
            QueueEntry.status == "notified",
            QueueEntry.expires_at < now,
        )
        .all()
    )
    user_ids = []
    for entry in expired:
        entry.status = "waiting"
        entry.created_at = now  # move to back of queue
        entry.notified_at = None
        entry.expires_at = None
        user_ids.append(entry.user_id)
    if expired:
        db.commit()
    return user_ids


def get_next_waiter(db: Session, gender: str) -> QueueEntry | None:
    return (
        db.query(QueueEntry)
        .filter(QueueEntry.gender == gender, QueueEntry.status == "waiting")
        .order_by(QueueEntry.created_at)
        .first()
    )


def get_all_waiting(db: Session, gender: str) -> list[QueueEntry]:
    return (
        db.query(QueueEntry)
        .filter(QueueEntry.gender == gender, QueueEntry.status == "waiting")
        .order_by(QueueEntry.created_at)
        .all()
    )


def count_waiting(db: Session, gender: str) -> int:
    return (
        db.query(QueueEntry)
        .filter(QueueEntry.gender == gender, QueueEntry.status == "waiting")
        .count()
    )
