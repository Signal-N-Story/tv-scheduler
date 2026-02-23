"""ATC TV Scheduler — Configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # Database
    database_path: str = "./schedule.db"

    # Fallback layers
    cache_dir: str = "./cache"
    backup_json_path: str = "./schedule_backup.json"
    splash_html: str = "src/templates/splash.html"

    # Scheduling
    timezone: str = "America/Chicago"
    swap_hour: int = 0
    swap_minute: int = 0

    # TV display
    tv_refresh_interval_seconds: int = 60

    # Authentication (set API_KEY env var to enable; empty = auth disabled)
    api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Board types
    BOARD_MAINBOARD: str = "mainboard"
    BOARD_MODBOARD: str = "modboard"

    # Default version mapping
    MAINBOARD_DEFAULT_VERSION: str = "rx"
    MODBOARD_DEFAULT_VERSION: str = "mod"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cache_path(self) -> Path:
        path = Path(self.cache_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def default_version(self, board_type: str) -> str:
        if board_type == self.BOARD_MAINBOARD:
            return self.MAINBOARD_DEFAULT_VERSION
        return self.MODBOARD_DEFAULT_VERSION


settings = Settings()