import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Required environment variable {key!r} is not set")
    return value


TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY: str = _require("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

YANDEX_DISK_TOKEN: str = _require("YANDEX_DISK_TOKEN")
YANDEX_DISK_ROOT: str = os.getenv("YANDEX_DISK_ROOT", "/TelegramBot")

SUMMARY_TIME: str = os.getenv("SUMMARY_TIME", "09:00")
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")
SUMMARY_WINDOW_HOURS: int = int(os.getenv("SUMMARY_WINDOW_HOURS", "24"))

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "/app/data/bot.db")

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_PATH: str = os.getenv("LOG_PATH", "/app/logs/bot.log")

MESSAGE_RETENTION_DAYS: int = int(os.getenv("MESSAGE_RETENTION_DAYS", "30"))

# Ensure local directories exist when running outside Docker
for _dir in (Path(DATABASE_PATH).parent, Path(LOG_PATH).parent, Path("pending")):
    _dir.mkdir(parents=True, exist_ok=True)
