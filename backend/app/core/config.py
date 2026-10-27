from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/bilianalyzer.db"
    SECRET_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:5173"
    DATA_DIR: str = "./data"
    STATS_REFRESH_HOURS: float = 24.0

settings = Settings()
