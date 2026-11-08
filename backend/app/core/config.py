from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/bilianalyzer.db"
    SECRET_KEY: str = ""
    CORS_ORIGINS: str = "http://localhost:5173"
    DATA_DIR: str = "./data"
    # Creator profile/account snapshot interval. Video snapshots use an
    # age-based cadence and stop when this is set to 0.
    STATS_REFRESH_HOURS: float = 24.0
    # The site-wide chart feeds both current placements and high-water ranks.
    # Poll frequently enough to observe intraday moves without hammering Bilibili.
    RANKING_REFRESH_MINUTES: float = 15.0
    # Scan each tracked creator's newest uploads for videos not yet in the
    # creator library.
    NEW_VIDEO_REFRESH_MINUTES: float = 30.0

settings = Settings()
