from fastapi import FastAPI
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
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
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
    return {"message": "Welcome to BI Pelampung API. Go to /docs for Swagger UI"}