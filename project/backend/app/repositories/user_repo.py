from sqlalchemy.orm import Session

from app.models.user import User


def get_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def create(db: Session, username: str, password_hash: str, gender: str) -> User:
    user = User(username=username, password_hash=password_hash, gender=gender)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user