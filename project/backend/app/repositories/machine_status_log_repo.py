from sqlalchemy.orm import Session

from app.models.machine import Machine, MachineStatusLog


def create(
    db: Session,
    machine: Machine,
    status: str,
    source: str,
    *,
    previous_status: str | None = None,
    changed_by_user_id: int | None = None,
    is_running: bool | None = None,
    changed: bool = False,
) -> MachineStatusLog:
    log = MachineStatusLog(
        machine_id=machine.id,
        previous_status=previous_status,
        status=status,
        changed_by_user_id=changed_by_user_id,
        source=source,
        is_running=is_running,
        changed=changed,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_for_machine(db: Session, machine_id: int, limit: int = 100) -> list[MachineStatusLog]:
    return (
        db.query(MachineStatusLog)
        .filter(MachineStatusLog.machine_id == machine_id)
        .order_by(MachineStatusLog.changed_at.desc(), MachineStatusLog.id.desc())
        .limit(limit)
        .all()
    )
