from sqlalchemy import Boolean, Column, Integer, String, Enum
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    gender = Column(Enum("male", "female", name="gender_enum"), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    email = Column(String(255), unique=True, nullable=True, index=True)
    is_verified = Column(Boolean, nullable=False, default=False)