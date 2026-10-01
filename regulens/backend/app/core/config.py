from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg2://regulens:regulens@localhost:5432/regulens"
    SECRET_KEY: str  # required: no default so secrets never live in source code
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    RESET_TOKEN_EXPIRE_MINUTES: int = 15

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384

    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 50
    CORS_ORIGINS: str = "http://localhost:5173"

    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    RETENTION_DAYS: int = 0
    DEBUG_RETURN_RESET_TOKEN: bool = False


settings = Settings()
