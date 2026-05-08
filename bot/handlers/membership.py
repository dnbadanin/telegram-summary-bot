import logging

from telegram import Update, ChatMember
from telegram.ext import ContextTypes

from bot.services.database import upsert_chat, set_chat_active

logger = logging.getLogger(__name__)


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    event = update.my_chat_member
    if not event:
        return

    chat = event.chat
    new_status = event.new_chat_member.status

    if new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR):
        await upsert_chat(chat.id, chat.title or "", chat.type)
        logger.info("Bot added to chat %s (%s)", chat.title, chat.id)
    elif new_status in (ChatMember.LEFT, ChatMember.BANNED):
        await set_chat_active(chat.id, False)
        logger.info("Bot removed from chat %s (%s)", chat.title, chat.id)
