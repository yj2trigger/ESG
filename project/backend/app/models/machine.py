from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
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
    reserved_until = Column(DateTime, nullable=True)

    reserved_by = relationship("User", foreign_keys=[reserved_by_user_id])