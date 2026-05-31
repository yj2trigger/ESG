from sqlalchemy import Column, Float, String

from app.core.database import Base


class SystemSettings(Base):
    __tablename__ = "system_settings"

    key = Column(String(64), primary_key=True)
    value_float = Column(Float, nullable=True)
    value_str = Column(String(1024), nullable=True)
