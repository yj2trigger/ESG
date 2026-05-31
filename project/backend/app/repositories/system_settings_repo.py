from sqlalchemy.orm import Session

from app.models.system_settings import SystemSettings


def get_float(db: Session, key: str, default: float) -> float:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value_float if row and row.value_float is not None else default


def set_float(db: Session, key: str, value: float) -> None:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if row:
        row.value_float = value
    else:
        db.add(SystemSettings(key=key, value_float=value))
    db.commit()


def get_str(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return row.value_str if row and row.value_str is not None else default


def set_str(db: Session, key: str, value: str) -> None:
    row = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if row:
        row.value_str = value
    else:
        db.add(SystemSettings(key=key, value_str=value))
    db.commit()
