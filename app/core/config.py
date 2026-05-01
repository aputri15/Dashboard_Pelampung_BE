from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "BI Dashboard Pelampung"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "super-secret-key-change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///./dashboard.db"

    class Config:
        case_sensitive = True

settings = Settings()