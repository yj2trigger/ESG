from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.machine import Machine


def get_all(db: Session) -> list[Machine]:
    return db.query(Machine).order_by(Machine.floor, Machine.machine_number).all()


def get_by_id(db: Session, machine_id: int) -> Machine | None:
    return db.query(Machine).filter(Machine.id == machine_id).first()


def set_status(db: Session, machine: Machine, new_status: str) -> Machine:
    # 세탁기가 실제 사용 중으로 전환 시 해당 사용자의 대기열 항목 제거
    if new_status == "in_use" and machine.reserved_by_user_id:
        from app.repositories.queue_repo import leave
        leave(db, machine.reserved_by_user_id)

    machine.status = new_status
    if new_status == "available":
        machine.reserved_by_user_id = None
        machine.reserved_until = None
    db.commit()
    db.refresh(machine)
    return machine


def count_available(db: Session, gender: str) -> int:
    """Count machines accessible to gender that are currently available (including expired soft_reserved)."""
    now = datetime.now(timezone.utc)
    return (
        db.query(func.count(Machine.id))
        .filter(
            Machine.status.in_(["available", "soft_reserved"]),
            (Machine.gender_restriction == gender) | (Machine.gender_restriction == None),  # noqa: E711
        )
        .filter(
            (Machine.status == "available")
            | ((Machine.status == "soft_reserved") & (Machine.reserved_until < now))
        )
        .scalar()
    ) or 0


def get_available_for_gender(db: Session, gender: str) -> list[Machine]:
    now = datetime.now(timezone.utc)
    return (
        db.query(Machine)
        .filter(
            (Machine.gender_restriction == gender) | (Machine.gender_restriction == None),  # noqa: E711
            (
                (Machine.status == "available")
                | ((Machine.status == "soft_reserved") & (Machine.reserved_until < now))
            ),
        )
        .all()
    )


def floor_available_counts(db: Session, gender: str) -> dict[int, int]:
    available = get_available_for_gender(db, gender)
    counts: dict[int, int] = {}
    for m in available:
        counts[m.floor] = counts.get(m.floor, 0) + 1
    return counts


def get_first_available(db: Session, gender: str) -> Machine | None:
    machines = get_available_for_gender(db, gender)
    return machines[0] if machines else None


def get_active_reserve(db: Session, user_id: int) -> Machine | None:
    """Return the user's current active (non-expired) soft_reserved machine, if any."""
    now = datetime.now(timezone.utc)
    return (
        db.query(Machine)
        .filter(
            Machine.status == "soft_reserved",
            Machine.reserved_by_user_id == user_id,
            Machine.reserved_until > now,
        )
        .first()
    )


def soft_reserve(db: Session, machine: Machine, user_id: int, duration_minutes: int = 10) -> Machine:
    machine.status = "soft_reserved"
    machine.reserved_by_user_id = user_id
    machine.reserved_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    db.commit()
    db.refresh(machine)
    return machine


def release_expired(db: Session) -> int:
    """Lazy expiration: release soft_reserved machines past their timer. Returns count released."""
    now = datetime.now(timezone.utc)
    expired = (
        db.query(Machine)
        .filter(Machine.status == "soft_reserved", Machine.reserved_until < now)
        .all()
    )
    for m in expired:
        m.status = "available"
        m.reserved_by_user_id = None
        m.reserved_until = None
    if expired:
        db.commit()
    return len(expired)


def seed(db: Session) -> None:
    """Insert dummy machines if the table is empty."""
    if db.query(func.count(Machine.id)).scalar():
        return

    machines: list[Machine] = []
    # 1~2층: 공용 9대 (각 층 4~5대)
    for floor in [1, 2]:
        count = 5 if floor == 1 else 4
        for num in range(1, count + 1):
            machines.append(Machine(floor=floor, machine_number=num, gender_restriction=None))

    # 3~5층: 남성 전용 1~2대
    for floor in [3, 4, 5]:
        count = 2 if floor == 3 else 1
        for num in range(1, count + 1):
            machines.append(Machine(floor=floor, machine_number=num, gender_restriction="male"))

    # 6~8층: 여성 전용 1~2대
    for floor in [6, 7, 8]:
        count = 2 if floor == 6 else 1
        for num in range(1, count + 1):
            machines.append(Machine(floor=floor, machine_number=num, gender_restriction="female"))

    db.add_all(machines)
    db.commit()