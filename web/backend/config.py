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
    # How many chunks the worker submits to the TTS server in parallel.
    # The server batches concurrent requests into one GPU forward pass, so raising
    # this is what fills the server's --max-batch and lifts GPU utilization.
    TTS_CONCURRENCY: int = 8
    # Some Qwen3-TTS voice-clone requests can exceed 5 minutes on an L4 when the
    # text chunk is large or the effective batch size is one.
    TTS_TIMEOUT: int = 1800
    ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]

    # Storage backend: "local" (default), "gcs", or "s3"
    STORAGE_BACKEND: str = "local"
    STORAGE_BUCKET: str = ""
    STORAGE_PREFIX: str = ""
    STORAGE_REGION: str = ""  # S3 region (e.g. us-east-1)
    STORAGE_LOCAL_CACHE_DIR: str = "/tmp/screencastgen_cache"

    model_config = {"env_prefix": "P2A_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
