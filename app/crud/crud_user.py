from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_conflicts(
    db: Session,
    username: Optional[str],
    email: Optional[str],
    exclude_user_id: Optional[int] = None,
) -> dict:
    query = db.query(User)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)

    username_exists = False
    email_exists = False

    if username:
        username_exists = query.filter(User.username == username).first() is not None

    query = db.query(User)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)

    if email:
        email_exists = query.filter(User.email == email).first() is not None

    return {"username": username_exists, "email": email_exists}

def is_last_active_admin(db: Session, db_user: User) -> bool:
    if db_user.role != "admin" or not db_user.is_active:
        return False
    active_admin_count = (
        db.query(User)
        .filter(User.role == "admin")
        .filter(User.is_active == True)  # noqa: E712
        .count()
    )
    return active_admin_count <= 1

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user_in: UserCreate) -> User:
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        full_name=user_in.full_name, email=user_in.email, username=user_in.username,
        hashed_password=hashed_password, role=user_in.role, is_active=user_in.is_active
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, db_user: User, user_in: UserUpdate) -> User:
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    for field, value in update_data.items():
        setattr(db_user, field, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int) -> Optional[User]:
    db_user = db.query(User).get(user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user