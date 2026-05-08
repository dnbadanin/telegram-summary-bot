import logging
from datetime import datetime, timedelta, timezone

from bot.config import SUMMARY_WINDOW_HOURS
from bot.services.database import (
    get_all_chats,
    get_messages_since,
    get_cached_summary,
    save_summary,
    get_subscribers,
    deactivate_subscription,
)
from bot.services.gemini import generate_summary
from bot.utils.text_formatter import format_messages_for_prompt, split_long_message

logger = logging.getLogger(__name__)


async def generate_and_cache_summary(chat: dict, target_date) -> str | None:
    chat_id = chat["chat_id"]
    chat_title = chat["chat_title"] or str(chat_id)

    cached = await get_cached_summary(chat_id, target_date)
    if cached:
        return cached

    since = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        hours=SUMMARY_WINDOW_HOURS
    )
    messages = await get_messages_since(chat_id, since)
    if not messages:
        return None

    formatted = format_messages_for_prompt(messages)
    date_str = target_date.strftime("%d.%m.%Y")
    try:
        summary = await generate_summary(chat_title, date_str, formatted, len(messages))
    except Exception as exc:
        logger.error("Failed to generate summary for chat %s: %s", chat_id, exc)
        return None

    await save_summary(chat_id, target_date, summary)
    return summary


async def deliver_summaries(app, target_date) -> None:
    chats = await get_all_chats()
    for chat in chats:
        try:
            await _deliver_for_chat(app, chat, target_date)
        except Exception as exc:
            logger.error("Error delivering summary for chat %s: %s", chat["chat_id"], exc)


async def _deliver_for_chat(app, chat: dict, target_date) -> None:
    chat_id = chat["chat_id"]
    summary = await generate_and_cache_summary(chat, target_date)
    if not summary:
        logger.info("No messages for chat %s on %s, skipping delivery", chat_id, target_date)
        return

    header = f"*Дайджест чата «{chat['chat_title']}» за {target_date.strftime('%d.%m.%Y')}*\n\n"
    full_text = header + summary
    parts = split_long_message(full_text)

    subscribers = await get_subscribers(chat_id)
    for user_id in subscribers:
        try:
            for part in parts:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=part,
                    parse_mode="Markdown",
                )
        except Exception as exc:
            err = str(exc).lower()
            if "blocked" in err or "forbidden" in err or "deactivated" in err:
                logger.warning("User %s blocked the bot, deactivating subscription", user_id)
                await deactivate_subscription(user_id, chat_id)
            else:
                logger.error("Failed to DM user %s: %s", user_id, exc)

    if chat.get("in_group_post"):
        try:
            for part in parts:
                await app.bot.send_message(
                    chat_id=chat_id,
                    text=part,
                    parse_mode="Markdown",
                )
        except Exception as exc:
            logger.error("Failed to post summary in group %s: %s", chat_id, exc)
