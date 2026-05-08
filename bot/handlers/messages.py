import logging
from datetime import datetime, timezone

from telegram import Update, PhotoSize
from telegram.ext import ContextTypes

from bot.services.database import upsert_chat, save_message
from bot.services.yandex_disk import upload_image, append_link
from bot.utils.link_extractor import extract_links

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not chat or chat.type not in ("group", "supergroup"):
        return

    await upsert_chat(chat.id, chat.title or "", chat.type)

    text = msg.text or msg.caption or ""
    links = extract_links(text)

    has_media = False
    media_type: str | None = None
    photo_data: bytes | None = None
    photo_filename: str | None = None

    if msg.photo:
        has_media = True
        media_type = "photo"
        largest: PhotoSize = max(msg.photo, key=lambda p: p.file_size or 0)
        try:
            file = await context.bot.get_file(largest.file_id)
            photo_data = await file.download_as_bytearray()
            photo_filename = f"{largest.file_unique_id}.jpg"
        except Exception as exc:
            logger.warning("Could not download photo from message %s: %s", msg.message_id, exc)
    elif msg.document and msg.document.mime_type and msg.document.mime_type.startswith("image/"):
        has_media = True
        media_type = "image_document"
        try:
            file = await context.bot.get_file(msg.document.file_id)
            photo_data = await file.download_as_bytearray()
            photo_filename = msg.document.file_name or f"{msg.document.file_unique_id}.jpg"
        except Exception as exc:
            logger.warning("Could not download image doc from message %s: %s", msg.message_id, exc)
    elif msg.video:
        has_media = True
        media_type = "video"
    elif msg.audio:
        has_media = True
        media_type = "audio"
    elif msg.voice:
        has_media = True
        media_type = "voice"
    elif msg.sticker:
        has_media = True
        media_type = "sticker"
    elif msg.document:
        has_media = True
        media_type = "document"

    timestamp = msg.date.replace(tzinfo=timezone.utc) if msg.date else datetime.now(timezone.utc)
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H:%M")

    await save_message(
        chat_id=chat.id,
        message_id=msg.message_id,
        user_id=user.id if user else 0,
        username=user.username if user else None,
        first_name=user.first_name if user else None,
        text=text or None,
        has_media=has_media,
        media_type=media_type,
        links=links,
        timestamp=timestamp,
    )

    if photo_data and photo_filename:
        await upload_image(
            chat.title or str(chat.id),
            date_str,
            msg.message_id,
            photo_filename,
            bytes(photo_data),
        )

    username = (user.username or user.first_name or str(user.id)) if user else "unknown"
    for url in links:
        context_snippet = text[:80] if text else ""
        await append_link(
            chat.title or str(chat.id),
            date_str,
            time_str,
            username,
            url,
            context_snippet,
        )
