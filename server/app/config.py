"""
Application configuration — loaded from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Server settings. Override via environment variables or .env file."""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Game settings
    TICK_RATE_SECONDS: float = 1.0  # Configurable turn duration
    MAX_PLAYERS_PER_MATCH: int = 8
    MIN_PLAYERS_TO_START: int = 2
    MATCH_TIMEOUT_MINUTES: int = 15
    MAP_DEFAULT: str = "arena_classic"
    GRID_WIDTH: int = 15
    GRID_HEIGHT: int = 15

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_prefix": "ARENA_", "env_file": ".env"}


settings = Settings()
