"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://screencastgen:screencastgen@localhost:5432/screencastgen"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://screencastgen:screencastgen@localhost:5432/screencastgen"
    REDIS_URL: str = "redis://localhost:6379/0"
    UPLOAD_DIR: str = "./uploads"
    OUTPUT_DIR: str = "./outputs"
    MAX_UPLOAD_SIZE_MB: int = 200
    TTS_SERVER_URL: str = "http://localhost:8100"
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = {"env_prefix": "P2A_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
