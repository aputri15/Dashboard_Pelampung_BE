import os

base_dir = r"c:\Users\ashila pe\Desktop\dashboard_bi_ta\dashboard_pelampung\backend"

files = {
    "requirements.txt": """fastapi==0.110.0
uvicorn==0.27.1
sqlalchemy==2.0.28
pydantic==2.6.3
pydantic-settings==2.2.1
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-multipart==0.0.9""",
    
    "app/__init__.py": "",
    "app/core/__init__.py": "",
    "app/db/__init__.py": "",
    "app/models/__init__.py": "",
    "app/schemas/__init__.py": "",
    "app/crud/__init__.py": "",
    "app/api/__init__.py": "",
    "app/api/v1/__init__.py": "",
    "app/api/v1/endpoints/__init__.py": "",

    "app/core/config.py": """from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "BI Dashboard Pelampung"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "super-secret-key-change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./dashboard.db"

    class Config:
        case_sensitive = True

settings = Settings()""",

    "app/core/security.py": """from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def create_refresh_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES))
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)""",

    "app/db/database.py": """from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()""",

    "app/models/user.py": """from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)""",

    "app/schemas/token.py": """from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: str = None
    type: str = None""",

    "app/schemas/user.py": """from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    username: str
    role: str
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDBBase(UserBase):
    id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    class Config:
        from_attributes = True

class UserResponse(UserInDBBase):
    pass""",

    "app/crud/crud_user.py": """from typing import Optional, List
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

def delete_user(db: Session, user_id: int) -> User:
    db_user = db.query(User).get(user_id)
    db.delete(db_user)
    db.commit()
    return db_user""",

    "app/api/deps.py": """from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.models.user import User
from app.schemas.token import TokenPayload
from app.crud.crud_user import get_user_by_username

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_current_user(db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)) -> User:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        token_data = TokenPayload(**payload)
        if token_data.type != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except (JWTError, ValidationError):
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    user = get_user_by_username(db, username=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def get_current_active_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user

def get_current_active_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user""",

    "app/api/v1/endpoints/auth.py": """from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from app.api import deps
from app.core import security
from app.core.config import settings
from app.crud import crud_user
from app.schemas.token import Token
from app.schemas.user import UserResponse

router = APIRouter()

@router.post("/login", response_model=Token)
def login_access_token(db: Session = Depends(deps.get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = crud_user.get_user_by_username(db, username=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    user.last_login = datetime.utcnow()
    db.commit()
    return {
        "access_token": security.create_access_token(user.username),
        "refresh_token": security.create_refresh_token(user.username),
        "token_type": "bearer",
    }

@router.post("/refresh", response_model=Token)
def refresh_token(refresh_token: str, db: Session = Depends(deps.get_db)):
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=400, detail="Invalid token structure")
    except JWTError:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
        
    user = crud_user.get_user_by_username(db, username=username)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid user")
    return {
        "access_token": security.create_access_token(user.username),
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user = Depends(deps.get_current_user)):
    return current_user""",

    "app/api/v1/endpoints/users.py": """from typing import Any, List
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
    return crud_user.delete_user(db, user_id=user_id)""",

    "app/api/v1/api.py": """from fastapi import APIRouter
from app.api.v1.endpoints import auth, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])""",

    "main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.db.database import engine, Base
from app.schemas.user import UserCreate
from app.crud.crud_user import get_user_by_username, create_user
from sqlalchemy.orm import Session
from app.db.database import SessionLocal

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.on_event("startup")
def create_initial_admin():
    db = SessionLocal()
    try:
        if not get_user_by_username(db, username="admin"):
            create_user(db, user_in=UserCreate(full_name="Admin Utama", email="admin@pelampung.com", username="admin", password="adminpassword", role="admin"))
            create_user(db, user_in=UserCreate(full_name="Owner Perusahaan", email="owner@pelampung.com", username="owner", password="ownerpassword", role="owner"))
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "Welcome to BI Pelampung API. Go to /docs for Swagger UI"}"""
}

for path, content in files.items():
    full_path = os.path.join(base_dir, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Project generated successfully!")
