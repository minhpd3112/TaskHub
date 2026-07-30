from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # App
    APP_NAME: str = "TaskHub API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database — required, no default
    DATABASE_URL: str  # postgresql+asyncpg://user:pass@host:5432/db
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis — required, no default
    REDIS_URL: str  # redis://localhost:6379/0

    # JWT — required, no default
    JWT_SECRET_KEY: str  # Must be provided via environment variables
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email (Cloud SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@taskhub.io"

    # Cache
    CACHE_TTL_TASKS: int = 300

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]


settings = Settings()
