import logging
from datetime import datetime, timezone, timedelta

from telegram import Update, ChatMember
from telegram.ext import ContextTypes

from bot.services.database import get_chat, set_in_group_post, count_today_messages, get_cached_summary

logger = logging.getLogger(__name__)


async def _is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False


async def cmd_enable_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_admin(update, context):
        await update.effective_message.reply_text("❌ Эта команда доступна только администраторам.")
        return
    chat = update.effective_chat
    await set_in_group_post(chat.id, True)
    await update.effective_message.reply_text(
        "✅ Публикация дайджеста в группе *включена*. Ежедневное резюме будет появляться прямо здесь.",
        parse_mode="Markdown",
    )


async def cmd_disable_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_admin(update, context):
        await update.effective_message.reply_text("❌ Эта команда доступна только администраторам.")
        return
    chat = update.effective_chat
    await set_in_group_post(chat.id, False)
    await update.effective_message.reply_text(
        "✅ Публикация дайджеста в группе *отключена*.",
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    db_chat = await get_chat(chat.id)
    if not db_chat:
        await update.effective_message.reply_text("Бот ещё не зарегистрировал этот чат.")
        return

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    today_count = await count_today_messages(chat.id, since)
    in_group = "включена" if db_chat.get("in_group_post") else "отключена"

    from datetime import date
    cached = await get_cached_summary(chat.id, date.today())
    last_summary = "есть (сегодня)" if cached else "ещё не сгенерировано"

    text = (
        f"*Статус бота в этом чате*\n\n"
        f"📨 Сообщений за последние 24 ч: *{today_count}*\n"
        f"📋 Последнее резюме: *{last_summary}*\n"
        f"📢 Публикация дайджеста в группе: *{in_group}*"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")
