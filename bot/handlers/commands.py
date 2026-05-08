import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.services.database import (
    add_subscription,
    remove_subscription,
    get_subscriptions,
    get_all_chats,
    get_chat,
)

logger = logging.getLogger(__name__)

_WELCOME = (
    "👋 Привет! Я бот-дайджест Telegram-чатов.\n\n"
    "Каждый день я буду отправлять тебе краткое резюме обсуждений из групп, на которые ты подписан.\n\n"
    "Команды:\n"
    "/subscribe <chat\\_id> — подписаться на дайджест чата\n"
    "/unsubscribe <chat\\_id> — отписаться\n"
    "/list — список твоих подписок\n"
    "/chats — список всех чатов, которые отслеживает бот\n"
    "/help — справка"
)

_HELP = (
    "*Доступные команды:*\n\n"
    "/start — приветственное сообщение\n"
    "/subscribe <chat\\_id> — подписаться на дайджест чата\n"
    "/unsubscribe <chat\\_id> — отписаться от дайджеста\n"
    "/list — список активных подписок\n"
    "/chats — чаты, которые отслеживает бот\n"
    "/help — эта справка"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(_WELCOME, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(_HELP, parse_mode="Markdown")


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not context.args:
        await msg.reply_text("Использование: /subscribe <chat\\_id>", parse_mode="Markdown")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await msg.reply_text("❌ Некорректный chat\\_id — должно быть целое число.", parse_mode="Markdown")
        return

    chat = await get_chat(chat_id)
    if not chat:
        await msg.reply_text(
            "❌ Бот не состоит в этом чате или чат ещё не зарегистрирован.\n"
            "Используй /chats чтобы посмотреть доступные чаты."
        )
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status in ("left", "kicked"):
            await msg.reply_text("❌ Ты должен быть участником этого чата.")
            return
    except Exception as exc:
        logger.warning("Could not verify membership for user %s in chat %s: %s", user.id, chat_id, exc)
        await msg.reply_text("⚠️ Не удалось проверить членство в чате. Попробуй позже.")
        return

    await add_subscription(user.id, chat_id)
    await msg.reply_text(
        f"✅ Подписка оформлена! Ты будешь получать ежедневный дайджест чата «{chat['chat_title']}»."
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message
    if not context.args:
        await msg.reply_text("Использование: /unsubscribe <chat\\_id>", parse_mode="Markdown")
        return

    try:
        chat_id = int(context.args[0])
    except ValueError:
        await msg.reply_text("❌ Некорректный chat\\_id.", parse_mode="Markdown")
        return

    await remove_subscription(user.id, chat_id)
    await msg.reply_text("✅ Подписка отменена.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    subs = await get_subscriptions(user.id)
    if not subs:
        await update.effective_message.reply_text("У тебя пока нет активных подписок.")
        return

    lines = ["*Твои подписки:*\n"]
    for s in subs:
        lines.append(f"• {s['chat_title']} (`{s['chat_id']}`)")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chats = await get_all_chats()
    if not chats:
        await update.effective_message.reply_text("Бот пока не добавлен ни в один чат.")
        return

    lines = ["*Чаты, которые отслеживает бот:*\n"]
    for c in chats:
        lines.append(f"• {c['chat_title']} (`{c['chat_id']}`)")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")
