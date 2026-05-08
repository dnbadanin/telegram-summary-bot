import logging
import logging.handlers
from pathlib import Path

from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters

from bot.config import TELEGRAM_BOT_TOKEN, LOG_LEVEL, LOG_PATH
from bot.services.database import init_db
from bot.services.scheduler import start_scheduler, stop_scheduler
from bot.handlers.messages import handle_message
from bot.handlers.commands import (
    cmd_start,
    cmd_help,
    cmd_subscribe,
    cmd_unsubscribe,
    cmd_list,
    cmd_chats,
)
from bot.handlers.admin import cmd_enable_summary, cmd_disable_summary, cmd_status


def _setup_logging() -> None:
    log_path = Path(LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Telegram Summary Bot")

    import asyncio

    async def _post_init(app) -> None:
        await init_db()
        start_scheduler(app)
        logger.info("Bot initialised and scheduler running")

    async def _post_shutdown(app) -> None:
        stop_scheduler()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    # Private-chat commands
    private = filters.ChatType.PRIVATE
    app.add_handler(CommandHandler("start", cmd_start, filters=private))
    app.add_handler(CommandHandler("help", cmd_help, filters=private))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe, filters=private))
    app.add_handler(CommandHandler("unsubscribe", cmd_unsubscribe, filters=private))
    app.add_handler(CommandHandler("list", cmd_list, filters=private))
    app.add_handler(CommandHandler("chats", cmd_chats, filters=private))

    # Group-admin commands
    group = filters.ChatType.GROUPS
    app.add_handler(CommandHandler("enable_summary", cmd_enable_summary, filters=group))
    app.add_handler(CommandHandler("disable_summary", cmd_disable_summary, filters=group))
    app.add_handler(CommandHandler("status", cmd_status, filters=group))

    # Collect all group messages
    app.add_handler(
        MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, handle_message)
    )

    logger.info("Handlers registered, starting polling")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
