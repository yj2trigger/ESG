from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    floor = Column(Integer, nullable=False)
    machine_number = Column(Integer, nullable=False)
    status = Column(
        Enum("available", "in_use", "soft_reserved", "broken", name="machine_status_enum"),
        nullable=False,
        default="available",
    )
    gender_restriction = Column(
        Enum("male", "female", name="machine_gender_enum"),
        nullable=True,
    )
    reserved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reserved_until = Column(DateTime(timezone=True), nullable=True)

    reserved_by = relationship("User", foreign_keys=[reserved_by_user_id])
    status_logs = relationship(
        "MachineStatusLog",
        back_populates="machine",
        cascade="all, delete-orphan",
    )


class MachineStatusLog(Base):
    __tablename__ = "machine_status_logs"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    source = Column(String(32), nullable=False, default="iot")
    is_running = Column(Boolean, nullable=True)
    changed = Column(Boolean, nullable=False, default=False)
    changed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    machine = relationship("Machine", back_populates="status_logs")
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])
