import os
from dataclasses import dataclass


@dataclass
class Settings:
    # API Hell Let Loose
    HLL_BASE_URL: str = os.getenv("HLL_BASE_URL", "http://76.13.113.27:7010/api")

    # PostgreSQL
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_NAME: str = os.getenv("DB_NAME", "hll_stats")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    # Discord
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Collector
    HISTORY_PAGES: int = int(os.getenv("HISTORY_PAGES", "5"))   # cuántas páginas traer por run
    PAGE_SIZE: int = int(os.getenv("PAGE_SIZE", "50"))

    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
