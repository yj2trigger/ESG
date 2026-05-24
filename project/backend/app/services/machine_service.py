from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import machine_repo
from app.schemas.machine import FloorSummary, MachineDetail, MachineMode, MachineRequestResponse, MachinesResponse


def get_current_mode(db: Session, gender: str) -> MachineMode:
    available = machine_repo.count_available(db, gender)
    if available >= 4:
        return "A"
    elif available >= 1:
        return "B"
    else:
        return "C"


def get_dashboard(db: Session, gender: str) -> MachinesResponse:
    mode = get_current_mode(db, gender)
    floor_counts = machine_repo.floor_available_counts(db, gender)

    floors = [
        FloorSummary(floor=f, available_count=c)
        for f, c in sorted(floor_counts.items())
    ]

    return MachinesResponse(mode=mode, floors=floors)


def request_machine(db: Session, user: User) -> MachineRequestResponse:
    # Lazy-expire stale soft_reserved machines before mode check
    machine_repo.release_expired(db)

    mode = get_current_mode(db, user.gender)
    if mode != "B":
        raise HTTPException(status_code=400, detail=f"현재 Mode {mode}입니다. Mode B에서만 사용 가능합니다")

    machine = machine_repo.get_first_available(db, user.gender)
    if not machine:
        raise HTTPException(status_code=400, detail="이용 가능한 세탁기가 없습니다")

    reserved = machine_repo.soft_reserve(db, machine, user.id)
    return MachineRequestResponse(
        assigned_machine=MachineDetail.model_validate(reserved),
        reserved_until=reserved.reserved_until,
    )