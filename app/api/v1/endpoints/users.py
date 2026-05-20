from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.crud import crud_user
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter()

def _duplicate_message(conflicts: dict) -> str:
    if conflicts.get("username") and conflicts.get("email"):
        return "Tidak berhasil, username dan email telah digunakan."
    if conflicts.get("username"):
        return "Tidak berhasil, username telah digunakan."
    if conflicts.get("email"):
        return "Tidak berhasil, email telah digunakan."
    return "Tidak berhasil, data akun telah digunakan."

@router.get("/", response_model=List[UserResponse])
def read_users(db: Session = Depends(deps.get_db), skip: int = 0, limit: int = 100, current_user = Depends(deps.get_current_active_admin)) -> Any:
    return crud_user.get_users(db, skip=skip, limit=limit)

@router.post("/", response_model=UserResponse)
def create_user(*, db: Session = Depends(deps.get_db), user_in: UserCreate, current_user = Depends(deps.get_current_active_admin)) -> Any:
    conflicts = crud_user.get_user_conflicts(
        db,
        username=user_in.username,
        email=user_in.email,
        exclude_user_id=None,
    )
    if conflicts["username"] or conflicts["email"]:
        raise HTTPException(status_code=400, detail=_duplicate_message(conflicts))
    if user_in.role not in ["admin", "owner"]:
        raise HTTPException(status_code=400, detail="Role hanya boleh admin atau owner.")
    return crud_user.create_user(db, user_in=user_in)

@router.put("/{user_id}", response_model=UserResponse)
def update_user(*, db: Session = Depends(deps.get_db), user_id: int, user_in: UserUpdate, current_user = Depends(deps.get_current_active_admin)) -> Any:
    user = crud_user.get_user(db, user_id=user_id)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user_in.role is not None and user_in.role not in ["admin", "owner"]:
        raise HTTPException(status_code=400, detail="Role hanya boleh admin atau owner.")

    conflicts = crud_user.get_user_conflicts(
        db,
        username=user_in.username,
        email=user_in.email,
        exclude_user_id=user_id,
    )
    if conflicts["username"] or conflicts["email"]:
        raise HTTPException(status_code=400, detail=_duplicate_message(conflicts))

    if crud_user.is_last_active_admin(db, user):
        demoting_last_admin = user_in.role is not None and user_in.role != "admin"
        deactivating_last_admin = user_in.is_active is False
        if demoting_last_admin or deactivating_last_admin:
            raise HTTPException(
                status_code=400,
                detail="Tidak berhasil, sistem harus memiliki minimal satu admin aktif.",
            )

    return crud_user.update_user(db, db_user=user, user_in=user_in)

@router.delete("/{user_id}", response_model=UserResponse)
def delete_user(*, db: Session = Depends(deps.get_db), user_id: int, current_user = Depends(deps.get_current_active_admin)) -> Any:
    user = crud_user.get_user(db, user_id=user_id)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id: raise HTTPException(status_code=400, detail="Cannot delete yourself")
    if crud_user.is_last_active_admin(db, user):
        raise HTTPException(
            status_code=400,
            detail="Tidak berhasil, sistem harus memiliki minimal satu admin aktif.",
        )
    return crud_user.delete_user(db, user_id=user_id)
