import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    "/subscribe — подписаться на дайджест чата\n"
    "/unsubscribe — отписаться\n"
    "/list — список твоих подписок\n"
    "/chats — список всех чатов, которые отслеживает бот\n"
    "/help — справка"
)

_HELP = (
    "*Доступные команды:*\n\n"
    "/start — приветственное сообщение\n"
    "/subscribe — подписаться на дайджест чата\n"
    "/unsubscribe — отписаться от дайджеста\n"
    "/list — список активных подписок\n"
    "/chats — чаты, которые отслеживает бот\n"
    "/help — эта справка"
)


def _chats_keyboard(chats: list[dict], callback_prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(c["chat_title"], callback_data=f"{callback_prefix}:{c['chat_id']}")]
        for c in chats
    ]
    return InlineKeyboardMarkup(buttons)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(_WELCOME, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(_HELP, parse_mode="Markdown")


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message

    # Direct usage with chat_id argument (backward-compatible)
    if context.args:
        try:
            chat_id = int(context.args[0])
        except ValueError:
            await msg.reply_text("❌ Некорректный chat\\_id — должно быть целое число.", parse_mode="Markdown")
            return
        await _do_subscribe(context, msg, user.id, chat_id)
        return

    chats = await get_all_chats()
    if not chats:
        await msg.reply_text("Бот пока не добавлен ни в один чат.")
        return

    subs = await get_subscriptions(user.id)
    subscribed_ids = {s["chat_id"] for s in subs}
    available = [c for c in chats if c["chat_id"] not in subscribed_ids]

    if not available:
        await msg.reply_text("Ты уже подписан на все доступные чаты.")
        return

    await msg.reply_text(
        "Выбери чат для подписки:",
        reply_markup=_chats_keyboard(available, "sub"),
    )


async def cmd_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    msg = update.effective_message

    if context.args:
        try:
            chat_id = int(context.args[0])
        except ValueError:
            await msg.reply_text("❌ Некорректный chat\\_id.", parse_mode="Markdown")
            return
        await remove_subscription(user.id, chat_id)
        await msg.reply_text("✅ Подписка отменена.")
        return

    subs = await get_subscriptions(user.id)
    if not subs:
        await msg.reply_text("У тебя нет активных подписок.")
        return

    chats = [{"chat_id": s["chat_id"], "chat_title": s["chat_title"]} for s in subs]
    await msg.reply_text(
        "Выбери чат для отписки:",
        reply_markup=_chats_keyboard(chats, "unsub"),
    )


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    subs = await get_subscriptions(user.id)
    if not subs:
        await update.effective_message.reply_text("У тебя пока нет активных подписок.")
        return

    lines = ["*Твои подписки:*\n"]
    for s in subs:
        lines.append(f"• {s['chat_title']}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chats = await get_all_chats()
    if not chats:
        await update.effective_message.reply_text("Бот пока не добавлен ни в один чат.")
        return

    lines = ["*Чаты, которые отслеживает бот:*\n"]
    for c in chats:
        lines.append(f"• {c['chat_title']}")
    await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown")


async def callback_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    action, chat_id_str = query.data.split(":", 1)
    chat_id = int(chat_id_str)
    user = update.effective_user

    if action == "sub":
        await _do_subscribe(context, query, user.id, chat_id)
    elif action == "unsub":
        await remove_subscription(user.id, chat_id)
        chat = await get_chat(chat_id)
        title = chat["chat_title"] if chat else str(chat_id)
        await query.edit_message_text(f"✅ Подписка на «{title}» отменена.")


async def _do_subscribe(context, reply_target, user_id: int, chat_id: int) -> None:
    chat = await get_chat(chat_id)
    if not chat:
        await reply_target.reply_text(
            "❌ Бот не состоит в этом чате или чат ещё не зарегистрирован."
        )
        return

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ("left", "kicked"):
            await reply_target.reply_text("❌ Ты должен быть участником этого чата.")
            return
    except Exception as exc:
        logger.warning("Could not verify membership for user %s in chat %s: %s", user_id, chat_id, exc)
        await reply_target.reply_text("⚠️ Не удалось проверить членство в чате. Попробуй позже.")
        return

    await add_subscription(user_id, chat_id)

    text = f"✅ Подписка оформлена! Ты будешь получать ежедневный дайджест чата «{chat['chat_title']}»."
    if hasattr(reply_target, "edit_message_text"):
        await reply_target.edit_message_text(text)
    else:
        await reply_target.reply_text(text)
