"""
config/settings.py  –  Configuración centralizada via variables de entorno
"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    # Base de datos
    DB_HOST:     str = os.environ.get("DB_HOST", "localhost")
    DB_PORT:     int = int(os.environ.get("DB_PORT", 5432))
    DB_NAME:     str = os.environ.get("DB_NAME", "railway")
    DB_USER:     str = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")

    # HLL API
    HLL_BASE_URL: str = os.environ.get("HLL_BASE_URL", "")

    # Discord webhook
    DISCORD_WEBHOOK_URL: str = os.environ.get("DISCORD_WEBHOOK_URL", "")

    # Discord Bot
    BOT_TOKEN:      str = os.environ.get("BOT_TOKEN", "")
    APPLICATION_ID: int = int(os.environ.get("APPLICATION_ID", 0))
    GUILD_ID:       int = int(os.environ.get("GUILD_ID", 0))
    CHANNEL_ID:     int = int(os.environ.get("CHANNEL_ID", 0))

    # Collector
    HISTORY_PAGES: int = int(os.environ.get("HISTORY_PAGES", 5))
    PAGE_SIZE:     int = int(os.environ.get("PAGE_SIZE", 50))


settings = Settings()