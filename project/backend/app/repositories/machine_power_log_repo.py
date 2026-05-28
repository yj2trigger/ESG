from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.machine import MachinePowerLog


def create(db: Session, machine_id: int, power_w: float) -> MachinePowerLog:
    log = MachinePowerLog(machine_id=machine_id, power_w=power_w)
    db.add(log)
    db.commit()
    return log


def get_history(db: Session, machine_id: int, hours: int = 24) -> list[MachinePowerLog]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.query(MachinePowerLog)
        .filter(
            MachinePowerLog.machine_id == machine_id,
            MachinePowerLog.recorded_at >= cutoff,
        )
        .order_by(MachinePowerLog.recorded_at.asc())
        .all()
    )


def delete_old(db: Session, days: int = 7) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = (
        db.query(MachinePowerLog)
        .filter(MachinePowerLog.recorded_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
