"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars or .env file. No secrets in code."""

    DATABASE_URL: str = "sqlite:///./dev.db"
    STORAGE_DIR: Path = Path("./storage")
    MAX_RECIPIENTS_PER_JOB: int = 1000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
