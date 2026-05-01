from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.crud import crud_user
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def read_users(db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100, current_user = Depends(deps.get_current_active_admin)) -> Any:
    return crud_user.get_users(db, skip=skip, limit=limit)

@router.post("/", response_model=UserResponse)
def create_user(*, db: Session = Depends(deps.get_db), user_in: UserCreate, current_user = Depends(deps.get_current_active_admin)) -> Any:
    if crud_user.get_user_by_email(db, email=user_in.email) or crud_user.get_user_by_username(db, username=user_in.username):
        raise HTTPException(status_code=400, detail="User exists")
    if user_in.role not in ["admin", "owner"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    return crud_user.create_user(db, user_in=user_in)

@router.put("/{user_id}", response_model=UserResponse)
def update_user(*, db: Session = Depends(deps.get_db), user_id: int, user_in: UserUpdate, current_user = Depends(deps.get_current_active_admin)) -> Any:
    user = crud_user.get_user(db, user_id=user_id)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return crud_user.update_user(db, db_user=user, user_in=user_in)

@router.delete("/{user_id}", response_model=UserResponse)
def delete_user(*, db: Session = Depends(deps.get_db), user_id: int, current_user = Depends(deps.get_current_active_admin)) -> Any:
    user = crud_user.get_user(db, user_id=user_id)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id: raise HTTPException(status_code=400, detail="Cannot delete yourself")
    return crud_user.delete_user(db, user_id=user_id)